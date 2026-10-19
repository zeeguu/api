"""
Run a cron task inside a Sentry transaction, so the calls it makes (HTTP,
database, LLM) are recorded as spans, the same way API requests are.
Without a transaction, Sentry only sees a task's errors.

Every run is also recorded for /status (see task_status).

Usage (run_task.sh does this):
    python -m zeeguu.operations.traced_task <task_name> <script.py> [args...]

The transaction is named "task:<task_name>"; the live component map uses
that name to tell which cron job made a call.
"""

import os
import runpy
import sys
import time

import sentry_sdk

import zeeguu.api.app  # noqa: F401 -- initializes Sentry when SENTRY_DSN is set
from zeeguu.operations import task_status


def main():
    task_name, script, *args = sys.argv[1:]

    # Look like `python script.py args`: the script sees its own argv and
    # can import modules next to it.
    sys.argv = [script, *args]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))

    exit_code = 0
    error = None
    started_at = time.time()
    try:
        # sampled=True: cron runs are few, so trace every one rather than the API's 30%
        with sentry_sdk.start_transaction(
            op="task", name=f"task:{task_name}", sampled=True
        ) as transaction:
            try:
                runpy.run_path(script, run_name="__main__")
                transaction.set_status("ok")
            except SystemExit as e:
                # A script calling sys.exit(0) is a success, not an exception
                exit_code = e.code
                transaction.set_status("ok" if e.code in (None, 0) else "internal_error")
    except Exception as e:
        error = f"{type(e).__name__}: {e}"[:300]
        raise
    finally:
        task_status.record(task_name, started_at, time.time(), exit_code, error)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
