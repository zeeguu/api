"""
The last run of every cron task, for /status (and the daily health digest).

traced_task records each run to <TASK_STATUS_DIR>/<task>.json: when it ran,
how long it took, whether it exited cleanly, and a one-line summary the task
sets itself with set_summary(). This replaces the report emails the tasks used
to send to the team address, which Gmail filed under Sent only.

TASK_STATUS_DIR is on the /zeeguu-data volume that both the run_task
containers and the API share.
"""

import json
import os
import statistics
import time

TASK_STATUS_DIR = os.environ.get("TASK_STATUS_DIR", "/zeeguu-data/tasks")

# Start times kept per task, to learn its usual interval
_HISTORY = 10

_summary = None


def set_summary(text):
    """One line saying what this run did, shown next to the task on /status."""
    global _summary
    _summary = text


def record(task_name, started_at, finished_at, exit_code, error=None):
    path = os.path.join(TASK_STATUS_DIR, f"{task_name}.json")
    try:
        previous = _read(path) or {}
        history = (previous.get("history") or []) + [started_at]
        run = {
            "task": task_name,
            "started_at": started_at,
            "duration_s": round(finished_at - started_at),
            "ok": exit_code in (None, 0) and error is None,
            "exit_code": exit_code,
            "error": error,
            "summary": _summary,
            "history": history[-_HISTORY:],
        }
        os.makedirs(TASK_STATUS_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(run, f)
        os.replace(tmp, path)
    except Exception as e:
        # Recording is a side channel: it must never fail the task itself
        print(f"task_status: could not record {task_name}: {e}")


def read_all(now=None):
    """Every recorded task, most recently run first, each with `late`: its
    last start is well past its usual interval (learned from its history)."""
    now = now or time.time()
    try:
        names = sorted(f for f in os.listdir(TASK_STATUS_DIR) if f.endswith(".json"))
    except OSError:
        return []
    runs = [r for r in (_read(os.path.join(TASK_STATUS_DIR, n)) for n in names) if r]
    # A record without a start time can't be shown or judged; skip it rather
    # than break /status
    runs = [r for r in runs if isinstance(r.get("started_at"), (int, float))]
    for r in runs:
        interval = _usual_interval(r.get("history") or [])
        r["late"] = bool(interval) and now - r["started_at"] > 1.5 * interval + 600
    return sorted(runs, key=lambda r: -r["started_at"])


def _usual_interval(history):
    gaps = [b - a for a, b in zip(history, history[1:]) if b > a]
    return statistics.median(gaps) if len(gaps) >= 2 else None


def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None
