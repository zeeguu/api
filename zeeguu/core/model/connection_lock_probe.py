"""
Who holds a MySQL connection when mysqlclient says "This connection is already
in use from another thread"?

mysqlclient 2.3.0 takes a per-connection lock without waiting and raises that
error whenever the lock is held, by any thread, the same one included.
connection_thread_guard can't see these failures: they happen inside
store_result() and next_result(), not in SQLAlchemy's query events.

This probe notes on each connection which threads are inside it, and in which
method. When the error fires it prints them and their stacks to stderr
("[connection-lock-probe]"); the error is re-raised unchanged. Remove it
together with connection_thread_guard once the cause is fixed.
"""

import functools
import sys
import threading
import traceback

_METHODS = ("query", "store_result", "next_result", "rollback", "ping")


def install():
    from MySQLdb.connections import Connection

    patch(Connection)


def patch(cls):
    if getattr(cls, "_zeeguu_lock_probe", False):
        return
    cls._zeeguu_lock_probe = True
    for name in _METHODS:
        setattr(cls, name, _wrap(name, getattr(cls, name)))


def _wrap(name, method):
    @functools.wraps(method)
    def probed(self, *args, **kwargs):
        inside = self.__dict__.setdefault("_zeeguu_inside", [])
        me = (threading.get_ident(), threading.current_thread().name, name)
        inside.append(me)
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            # once per error: on re-entry it passes through two probed calls
            if "already in use from another thread" in str(e) and not hasattr(e, "_zeeguu_reported"):
                e._zeeguu_reported = True
                _report(me, [x for x in inside if x is not me])
            raise
        finally:
            inside.remove(me)

    return probed


def _report(me, holders):
    try:
        held_by = [f"{name} in {method}()" for _, name, method in holders] or "nobody we saw"
        lines = [
            f"[connection-lock-probe] {me[1]} in {me[2]}(): connection held by {held_by}\n",
            "--- this thread:\n",
            *traceback.format_stack(),
        ]
        frames = sys._current_frames()
        for ident, name, method in holders:
            if ident != me[0] and ident in frames:
                lines += [f"--- {name}, inside {method}():\n", *traceback.format_stack(frames[ident])]
        print("".join(lines), file=sys.stderr, flush=True)
    except Exception as e:  # diagnostics must never change the error the caller sees
        print(f"[connection-lock-probe] could not report: {e!r}", file=sys.stderr)
