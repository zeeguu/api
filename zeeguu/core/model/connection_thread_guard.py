"""
Report when a pooled DB connection is used by a thread other than the one
that checked it out.

Since 2026-09-28 production has raised "This connection is already in use
from another thread" (mysqlclient >= 2.3.0, which added that check) on ~16
endpoints, plus "Commands out of sync" from the same minute. Both mean two
threads used one MySQL connection, but the failing frame is only ever the
victim's ordinary query: the other thread is invisible. This guard names it.

Every pool checkout records the owning thread (and where it checked out). A
query, or the check-in rollback, on a different thread is reported to Sentry
and stderr with three stacks: the offending thread now, the owner thread now,
and the owner's checkout. Diagnostics only: it never raises and never blocks
the query. Remove it once the cause is found and fixed.
"""

import sys
import threading
import time
import traceback

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

_THIS_FILE = "model/connection_thread_guard.py"
_OWNER = "zeeguu_owner_thread"
_CHECKOUT_STACK = "zeeguu_checkout_stack"

# One report per call site per interval: if a site does this on every request,
# the first stacks say everything and the rest would only flood Sentry.
REPORT_INTERVAL_SECONDS = 600
_last_report = {}
_last_report_lock = threading.Lock()


def install():
    """Listen on every Pool and Engine. Safe to call more than once."""
    if not event.contains(Pool, "checkout", _on_checkout):
        event.listen(Pool, "checkout", _on_checkout)
        event.listen(Pool, "checkin", _on_checkin)
        event.listen(Engine, "before_cursor_execute", _on_execute)


def uninstall():
    if event.contains(Pool, "checkout", _on_checkout):
        event.remove(Pool, "checkout", _on_checkout)
        event.remove(Pool, "checkin", _on_checkin)
        event.remove(Engine, "before_cursor_execute", _on_execute)


def _on_checkout(dbapi_connection, connection_record, connection_proxy):
    connection_record.info[_OWNER] = (threading.get_ident(), threading.current_thread().name)
    connection_record.info[_CHECKOUT_STACK] = traceback.extract_stack(limit=30)[:-1]


def _on_checkin(dbapi_connection, connection_record):
    # The pool has just rolled the connection back ("reset on return"); if the
    # garbage collector returned an abandoned connection, that ran on its thread.
    try:
        _check(connection_record.info, "checkin (rollback on return)", statement=None)
    finally:
        connection_record.info.pop(_OWNER, None)
        connection_record.info.pop(_CHECKOUT_STACK, None)


def _on_execute(conn, cursor, statement, parameters, context, executemany):
    try:
        info = conn.connection.info
    except Exception:
        return
    _check(info, "query", statement)


def _check(info, kind, statement):
    try:
        owner = info.get(_OWNER)
        if owner is None or owner[0] == threading.get_ident():
            return
        _report(info, owner, kind, statement)
    except Exception as e:  # diagnostics must never break a request
        print(f"[connection-thread-guard] failed to check: {e!r}", file=sys.stderr)


def _report(info, owner, kind, statement):
    here = [f for f in traceback.extract_stack() if not f.filename.endswith(_THIS_FILE)]
    site = _site(here)
    now = time.monotonic()
    with _last_report_lock:
        if now - _last_report.get(site, -REPORT_INTERVAL_SECONDS) < REPORT_INTERVAL_SECONDS:
            return
        _last_report[site] = now

    owner_ident, owner_name = owner
    owner_frame = sys._current_frames().get(owner_ident)
    owner_now = traceback.format_stack(owner_frame) if owner_frame else ["(owner thread has exited)\n"]
    checkout = traceback.format_list(info.get(_CHECKOUT_STACK) or [])
    current = threading.current_thread().name
    title = (f"DB connection used by thread {current!r}, checked out by {owner_name!r}"
             f" ({kind}) at {site}")

    print(
        f"[connection-thread-guard] {title}\n"
        f"statement: {(statement or '')[:300]}\n"
        f"--- this thread ({current}):\n{''.join(traceback.format_list(here))}"
        f"--- owner thread now ({owner_name}):\n{''.join(owner_now)}"
        f"--- owner checked it out at:\n{''.join(checkout)}",
        file=sys.stderr,
    )
    sys.stderr.flush()

    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("connection_thread_guard", kind)
            scope.set_context("connection_thread_guard", {
                "statement": (statement or "")[:300],
                "this_thread": current,
                "owner_thread": owner_name,
                "this_stack": "".join(traceback.format_list(here))[-6000:],
                "owner_stack_now": "".join(owner_now)[-6000:],
                "owner_checkout_stack": "".join(checkout)[-6000:],
            })
            scope.fingerprint = ["connection-thread-guard", kind, site]
            sentry_sdk.capture_message(title, level="error")
    except Exception as e:
        print(f"[connection-thread-guard] could not report to Sentry: {e!r}", file=sys.stderr)


def _site(stack):
    """The innermost frame in our own code, so reports group by call site."""
    for frame in reversed(stack):
        path = frame.filename
        if "/zeeguu/" in path and "site-packages" not in path:
            return f"{path.rsplit('/zeeguu/', 1)[-1]}:{frame.lineno} {frame.name}"
    frame = stack[-1] if stack else None
    return f"{frame.filename}:{frame.lineno}" if frame else "unknown"
