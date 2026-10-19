from json import dumps, loads

from fixtures import logged_in_client as client
from zeeguu.core.model import UserActivityData


def _upload_click(client, seen):
    client.post(
        "/upload_user_activity_data",
        data=dict(
            time="2026-10-05T09:58:29.502Z",
            event="CLICKED ARTICLE",
            value="",
            extra_data=dumps(seen),
        ),
    )
    return UserActivityData.query.filter_by(event="CLICKED ARTICLE").one()


def test_click_after_deep_scroll_keeps_the_cards_just_above_it(client):
    # ~80 feed pages of 7-digit ids: three times the 4096-char column
    seen = list(range(2_600_000, 2_601_600))

    stored = _upload_click(client, seen)

    assert loads(stored.extra_data) == seen[-100:]


def test_short_seen_list_is_stored_as_sent(client):
    seen = [2765066, 2764361, 2764797]

    stored = _upload_click(client, seen)

    assert loads(stored.extra_data) == seen
