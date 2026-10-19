"""When mysqlclient refuses a connection as "already in use", the probe must say
who was inside it: another thread, the same thread, or nobody it saw."""
import threading

import pytest

from zeeguu.core.model import connection_lock_probe as probe

IN_USE = "This connection is already in use from another thread."


class FakeConnection:
    """Locks like mysqlclient 2.3.0: take the lock without waiting, refuse if
    anyone (this thread included) holds it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.during_query = lambda: None

    def _locked(self, fn):
        if not self.lock.acquire(blocking=False):
            raise RuntimeError(IN_USE)
        try:
            return fn()
        finally:
            self.lock.release()

    def query(self, q):
        return self._locked(self.during_query)

    def store_result(self):
        return self._locked(lambda: "result")

    def next_result(self):
        return self._locked(lambda: -1)

    def rollback(self):
        return self._locked(lambda: None)

    def ping(self):
        return self._locked(lambda: None)


probe.patch(FakeConnection)


def _probe_lines(capsys):
    return [l for l in capsys.readouterr().err.splitlines() if l.startswith("[connection-lock-probe]")]


def test_normal_use_is_silent(capsys):
    conn = FakeConnection()
    conn.query("SELECT 1")
    assert conn.store_result() == "result"
    assert _probe_lines(capsys) == []


def test_names_the_other_thread_inside(capsys):
    conn = FakeConnection()
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        release.wait(5)

    conn.during_query = slow
    other = threading.Thread(target=conn.query, args=("SELECT 1",), name="other")
    other.start()
    entered.wait(5)
    with pytest.raises(RuntimeError):
        conn.store_result()
    release.set()
    other.join()

    [line] = _probe_lines(capsys)
    assert "MainThread in store_result(): connection held by ['other in query()']" in line


def test_names_the_same_thread_reentering(capsys):
    conn = FakeConnection()
    conn.during_query = conn.next_result  # e.g. a finalizer closing a cursor mid-query
    with pytest.raises(RuntimeError):
        conn.query("SELECT 1")

    [line] = _probe_lines(capsys)
    assert "MainThread in next_result(): connection held by ['MainThread in query()']" in line


def test_says_nobody_when_the_lock_was_taken_unseen(capsys):
    conn = FakeConnection()
    conn.lock.acquire()  # held by something the probe doesn't wrap
    with pytest.raises(RuntimeError):
        conn.next_result()

    [line] = _probe_lines(capsys)
    assert "connection held by nobody we saw" in line
