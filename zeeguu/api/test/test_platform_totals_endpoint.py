import json

from fixtures import client


def test_totals_are_public_json(client):
    # no session: the research page calls this anonymously
    response = client.get("/stats/totals")
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"

    totals = json.loads(response.data)
    for key in ("lookups", "exercises", "learners", "reading_sessions", "languages", "teachers", "classes"):
        assert isinstance(totals[key], int)
    assert "computed_at" in totals


def _forget_in_memory_totals():
    from zeeguu.api.endpoints import user_stats

    user_stats._platform_totals.update(totals=None, computed_at=None)


def test_a_restarted_worker_reads_the_stored_totals(client, monkeypatch):
    _forget_in_memory_totals()
    first = json.loads(client.get("/stats/totals").data)

    def must_not_compute(session):
        raise AssertionError("recomputed although the database had the totals")

    monkeypatch.setattr(
        "zeeguu.core.user_statistics.platform_totals.compute_platform_totals", must_not_compute
    )
    _forget_in_memory_totals()
    assert json.loads(client.get("/stats/totals").data) == first


def test_stale_totals_are_served_and_then_refreshed(client):
    from datetime import datetime, timedelta
    from zeeguu.core.model import PlatformTotalsCache, db
    from zeeguu.api.endpoints import user_stats

    _forget_in_memory_totals()
    client.get("/stats/totals")
    day_old = datetime.now() - timedelta(days=2)
    entry = PlatformTotalsCache.latest()
    entry.computed_at = day_old
    db.session.commit()
    _forget_in_memory_totals()

    # served at once, stale; the refresh (inline under tests) updates the store
    stale = json.loads(client.get("/stats/totals").data)
    assert stale["computed_at"] == day_old.isoformat(timespec="seconds")
    assert PlatformTotalsCache.latest().computed_at > day_old
    assert user_stats._platform_totals["computed_at"] > day_old
