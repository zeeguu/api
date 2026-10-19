"""
Name who holds a MySQL connection when mysqlclient says "This connection is
already in use from another thread".

mysqlclient 2.3.0 guards each connection with a lock that it takes without
waiting (_mysql_ConnectionObject_Lock in _mysql.c) and raises that
ProgrammingError whenever the lock is already held -- also when the holder is
the *same* thread, despite the message. connection_thread_guard only sees
SQLAlchemy's queries and check-ins; it stayed silent through eight of these
errors (14-19 Oct 2026), all raised inside store_result() or inside
cursor.close() -> next_result(), which it doesn't see.

This probe wraps the lock-taking methods of MySQLdb's Connection, so at every
moment it knows which threads are inside each connection, and in which method.
When the error fires it reports to Sentry and stderr:
  - who is inside the connection: thread, method, and that thread's stack now
    (nobody = the lock was taken by something this probe doesn't wrap, or was
    never released)
  - the failing call's stack
  - the connection's last operations, with their threads
Diagnostics only: the original error is re-raised unchanged. Remove it together
with connection_thread_guard once the cause is found and fixed.
"""

import collections
import functools
import sys
import threading
import time
import traceback

from zeeguu.core.model.connection_thread_guard import REPORT_INTERVAL_SECONDS, _site

_THIS_FILE = "model/connection_lock_probe.py"
_IN_USE = "already in use from another thread"
_STATE = "_zeeguu_lock_probe"
_HISTORY_LENGTH = 20

# The Connection methods that take the connection lock, directly or through
# the Result object they create. Missing names are skipped.
_METHODS = (
    "query",
    "store_result",
    "use_result",
    "next_result",
    "discard_result",
    "string_literal",
    "escape",
    "escape_string",
    "ping",
    "commit",
    "rollback",
    "autocommit",
    "select_db",
    "set_character_set",
    "affected_rows",
    "insert_id",
    "warning_count",
    "field_count",
    "close",
)

_originals = {}  # (class, method name) -> original
_last_report = {}
_last_report_lock = threading.Lock()


class _State:
    def __init__(self):
        self.inside = []  # (thread ident, thread name, method), one per call in progress
        self.history = collections.deque(maxlen=_HISTORY_LENGTH)


def install():
    """Wrap MySQLdb's Connection. Safe to call more than once."""
    try:
        from MySQLdb.connections import Connection
    except ImportError:
        return
    patch(Connection)


def patch(cls):
    for name in _METHODS:
        method = getattr(cls, name, None)
        if method is None or (cls, name) in _originals:
            continue
        _originals[(cls, name)] = cls.__dict__.get(name)
        setattr(cls, name, _wrap(name, method))


def unpatch(cls):
    for (patched_cls, name), original in list(_originals.items()):
        if patched_cls is not cls:
            continue
        if original is None:
            delattr(cls, name)  # was inherited; drop our override
        else:
            setattr(cls, name, original)
        del _originals[(cls, name)]


def _state(conn):
    state = conn.__dict__.get(_STATE)
    if state is None:
        state = conn.__dict__.setdefault(_STATE, _State())
    return state


def _wrap(name, method):
    @functools.wraps(method)
    def probed(self, *args, **kwargs):
        state = _state(self)
        entry = (threading.get_ident(), threading.current_thread().name, name)
        state.history.append((time.time(), entry[1], name))
        state.inside.append(entry)
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            if _IN_USE in str(e):
                others = [x for x in state.inside if x is not entry]
                _report(state, entry, others)
            raise
        finally:
            state.inside.remove(entry)

    return probed


def _report(state, entry, others):
    try:
        here = [f for f in traceback.extract_stack() if not f.filename.endswith(_THIS_FILE)]
        site = _site(here)
        ident, current, method = entry
        if not others:
            holder = "nobody inside"
        elif all(x[0] == ident for x in others):
            holder = "this same thread"
        else:
            holder = "another thread"

        key = (site, holder)
        now = time.monotonic()
        with _last_report_lock:
            if now - _last_report.get(key, -REPORT_INTERVAL_SECONDS) < REPORT_INTERVAL_SECONDS:
                return
            _last_report[key] = now

        frames = sys._current_frames()
        held_by = []
        for other_ident, other_name, other_method in others:
            frame = frames.get(other_ident)
            if other_ident == ident:
                stack = "(this thread, see above)\n"
            elif frame:
                stack = "".join(traceback.format_stack(frame))
            else:
                stack = "(thread has exited)\n"
            held_by.append(f"--- inside: {other_name} in {other_method}():\n{stack}")
        inside = "".join(held_by) or "--- nobody inside\n"
        history = "".join(
            f"  {time.strftime('%H:%M:%S', time.gmtime(t))}.{int(t % 1 * 1000):03d}"
            f" {thread} {op}\n"
            for t, thread, op in state.history
        )

        title = f"Connection lock held ({holder}) when {current!r} called {method}() at {site}"
        print(
            f"[connection-lock-probe] {title}\n"
            f"--- this thread ({current}):\n{''.join(traceback.format_list(here))}"
            f"{inside}"
            f"--- last operations on this connection (UTC):\n{history}",
            file=sys.stderr,
        )
        sys.stderr.flush()

        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("connection_lock_probe", holder)
            scope.set_context("connection_lock_probe", {
                "this_thread": current,
                "method": method,
                "this_stack": "".join(traceback.format_list(here))[-6000:],
                "inside": inside[-6000:],
                "history": history[-6000:],
            })
            scope.fingerprint = ["connection-lock-probe", holder, site]
            sentry_sdk.capture_message(title, level="error")
    except Exception as e:  # diagnostics must never change the error the caller sees
        print(f"[connection-lock-probe] could not report: {e!r}", file=sys.stderr)
