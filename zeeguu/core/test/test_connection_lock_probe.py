"""When mysqlclient refuses a connection as "already in use", the probe must say
who was inside it: another thread, the same thread, or nobody it saw."""
import threading

import pytest

from zeeguu.core.model import connection_lock_probe as probe

IN_USE = (
    "This connection is already in use from another thread. "
    "Do not use the same connection object from multiple threads simultaneously."
)


class ProgrammingError(Exception):
    pass


class FakeConnection:
    """Locks like mysqlclient 2.3.0: take the lock without waiting, refuse if
    anyone (this thread included) holds it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.during_query = lambda: None

    def _locked(self, fn):
        if not self.lock.acquire(blocking=False):
            raise ProgrammingError(IN_USE)
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


@pytest.fixture
def reports(monkeypatch):
    seen = []
    monkeypatch.setattr(probe, "_last_report", {})
    real_report = probe._report

    def record(state, entry, others):
        seen.append((entry[2], [(name, method) for _, name, method in others]))
        real_report(state, entry, others)  # exercise the formatting too

    monkeypatch.setattr(probe, "_report", record)
    sent = []
    monkeypatch.setattr("sentry_sdk.capture_message", lambda title, **k: sent.append(title))
    probe.patch(FakeConnection)
    yield seen, sent
    probe.unpatch(FakeConnection)


def test_normal_use_is_silent(reports):
    seen, sent = reports
    conn = FakeConnection()
    conn.query("SELECT 1")
    assert conn.store_result() == "result"
    assert seen == []


def test_names_the_other_thread_inside(reports):
    seen, sent = reports
    conn = FakeConnection()
    entered, release = threading.Event(), threading.Event()

    def slow():
        entered.set()
        release.wait(5)

    conn.during_query = slow
    other = threading.Thread(target=conn.query, args=("SELECT 1",), name="other")
    other.start()
    entered.wait(5)
    with pytest.raises(ProgrammingError):
        conn.store_result()
    release.set()
    other.join()

    assert seen == [("store_result", [("other", "query")])]
    assert "another thread" in sent[0]


def test_names_the_same_thread_reentering(reports):
    seen, sent = reports
    conn = FakeConnection()
    conn.during_query = conn.next_result  # e.g. a finalizer closing a cursor mid-query
    with pytest.raises(ProgrammingError):
        conn.query("SELECT 1")

    assert seen[0] == ("next_result", [("MainThread", "query")])
    assert "this same thread" in sent[0]


def test_says_nobody_when_the_lock_was_taken_unseen(reports):
    seen, sent = reports
    conn = FakeConnection()
    conn.lock.acquire()  # held by something the probe doesn't wrap
    with pytest.raises(ProgrammingError):
        conn.next_result()

    assert seen == [("next_result", [])]
    assert "nobody inside" in sent[0]


def test_unpatch_restores_the_class(reports):
    probe.unpatch(FakeConnection)
    assert "probed" not in FakeConnection.query.__qualname__
    probe.patch(FakeConnection)  # the fixture unpatches again
