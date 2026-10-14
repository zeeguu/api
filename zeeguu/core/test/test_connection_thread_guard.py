"""The guard must name a thread that uses a pooled connection it didn't check
out, and stay silent for normal single-thread use."""
import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from zeeguu.core.model import connection_thread_guard as guard


@pytest.fixture
def reports(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(guard, "_last_report", {})
    real_report = guard._report

    def record(info, owner, kind, statement):
        seen.append((kind, owner[1], threading.current_thread().name))
        real_report(info, owner, kind, statement)  # exercise the formatting too

    monkeypatch.setattr(guard, "_report", record)
    sent = []
    monkeypatch.setattr("sentry_sdk.capture_message", lambda title, **k: sent.append(title))
    guard.install()
    engine = create_engine(
        f"sqlite:///{tmp_path}/guard.db",
        poolclass=QueuePool,
        connect_args={"check_same_thread": False},
    )
    yield engine, seen, sent
    engine.dispose()
    guard.uninstall()


def _in_thread(fn, name="other"):
    t = threading.Thread(target=fn, name=name)
    t.start()
    t.join()


def test_single_thread_use_is_silent(reports):
    engine, seen, sent = reports
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    assert seen == []


def test_query_from_another_thread_is_reported(reports):
    engine, seen, sent = reports
    with engine.connect() as conn:
        _in_thread(lambda: conn.execute(text("SELECT 1")))
    assert ("query", "MainThread", "other") in seen


def test_return_from_another_thread_is_reported(reports):
    engine, seen, sent = reports
    conn = engine.connect()
    _in_thread(conn.close)  # the pool's rollback-on-return runs in "other"
    assert ("checkin (rollback on return)", "MainThread", "other") in seen


def test_one_report_per_call_site(reports):
    engine, seen, sent = reports
    with engine.connect() as conn:
        for _ in range(3):
            _in_thread(lambda: conn.execute(text("SELECT 1")))
    assert len([r for r in seen if r[0] == "query"]) == 3  # noticed every time...
    assert len(sent) == 1                                   # ...sent to Sentry once
