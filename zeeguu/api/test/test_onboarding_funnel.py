"""The onboarding funnel: steps recorded before and after there is an account."""

import json

from fixtures import client, logged_in_client
from zeeguu.core.account_management.user_account_deletion import delete_user_account
from zeeguu.core.model import User
from zeeguu.core.model.db import db
from zeeguu.core.model.onboarding_funnel_event import OnboardingFunnelEvent
from zeeguu.core.util.user_agent import parse_user_agent

FUNNEL = "f2b6c0de-1111-4a4a-9c9c-0123456789ab"

IPHONE_INSTAGRAM = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 Instagram 323.0.3.23.54 (iPhone14,5; iOS 17_4)"
)


def _post(client, body, url="/onboarding_funnel_event", **headers):
    return client.post(url, data=json.dumps(body), headers=headers)


def _events():
    return OnboardingFunnelEvent.query.order_by(OnboardingFunnelEvent.id).all()


def test_a_step_is_recorded_without_a_session(client):
    response = _post(
        client,
        {
            "funnel_id": FUNNEL,
            "step": "account_form_shown",
            "entry_point": "landing",
            "detail": {"seconds_on_previous_step": 12},
            "platform": 2,
            "viewport_w": 391,
            "viewport_h": 664,
            "ui_language": "da-DK",
            "online": True,
        },
        **{"User-Agent": IPHONE_INSTAGRAM},
    )
    assert response.status_code == 200

    [event] = _events()
    assert (event.step, event.entry_point, event.user_id) == ("account_form_shown", "landing", None)
    assert event.detail == {"seconds_on_previous_step": 12}
    assert (event.viewport_w, event.viewport_h) == (390, 660)
    assert (event.os, event.os_version, event.browser) == ("ios", "17", "instagram")
    assert (event.platform, event.ui_language, event.online) == (2, "da-DK", True)


def test_a_beacon_without_a_json_content_type_is_accepted(client):
    response = client.post(
        "/onboarding_funnel_event",
        data=json.dumps({"funnel_id": FUNNEL, "step": "page_hidden"}),
        content_type="text/plain",
    )
    assert response.status_code == 200
    assert [e.step for e in _events()] == ["page_hidden"]


def test_malformed_events_are_rejected(client):
    for body in (
        {"step": "x"},
        {"funnel_id": "short", "step": "x"},
        {"funnel_id": FUNNEL, "step": "Not A Step"},
        {"funnel_id": FUNNEL, "step": "x", "detail": "not an object"},
        {"funnel_id": FUNNEL, "step": "x", "detail": {"blob": "a" * 2000}},
        {"funnel_id": FUNNEL, "step": "x", "entry_point": "<script>"},
    ):
        assert _post(client, body).status_code == 400, body
    assert _events() == []


def test_unknown_platform_and_junk_fields_are_dropped_not_stored(client):
    _post(
        client,
        {
            "funnel_id": FUNNEL,
            "step": "x",
            "platform": 99,
            "viewport_w": "wide",
            "online": "yes",
            "app_version": "1.3.11" + "9" * 100,
        },
    )
    [event] = _events()
    assert (event.platform, event.viewport_w, event.online) == (None, None, None)
    assert len(event.app_version) == 32


def test_a_session_claims_the_funnels_earlier_anonymous_steps(logged_in_client):
    _post(logged_in_client.client, {"funnel_id": FUNNEL, "step": "landing_viewed"})
    _post(logged_in_client.client, {"funnel_id": "someone-else-entirely", "step": "landing_viewed"})
    _post(
        logged_in_client.client,
        {"funnel_id": FUNNEL, "step": "account_created"},
        url=logged_in_client.append_session("/onboarding_funnel_event"),
    )

    user = User.find(logged_in_client.email)
    by_funnel = {(e.funnel_id, e.step): e.user_id for e in _events()}
    assert by_funnel == {
        (FUNNEL, "landing_viewed"): user.id,
        ("someone-else-entirely", "landing_viewed"): None,
        (FUNNEL, "account_created"): user.id,
    }


def test_deleting_the_account_deletes_its_funnel(logged_in_client):
    _post(
        logged_in_client.client,
        {"funnel_id": FUNNEL, "step": "account_created"},
        url=logged_in_client.append_session("/onboarding_funnel_event"),
    )
    delete_user_account(db.session, User.find(logged_in_client.email))
    assert _events() == []


def test_user_agents_of_interest():
    def family(ua):
        parsed = parse_user_agent(ua)
        return parsed["os"], parsed["browser"]

    assert family(IPHONE_INSTAGRAM) == ("ios", "instagram")
    assert family(
        "Mozilla/5.0 (Linux; Android 14; SM-A146B Build/UP1A; wv) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Version/4.0 Chrome/129.0.6668.81 Mobile Safari/537.36 "
        "[FB_IAB/FB4A;FBAV/484.0.0.53.70;]"
    ) == ("android", "facebook")
    assert family(
        "Mozilla/5.0 (Linux; Android 14; Pixel 7; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Version/4.0 Chrome/129.0.6668.81 Mobile Safari/537.36"
    ) == ("android", "android_webview")
    assert family(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Mobile/15E148"
    ) == ("ios", "ios_webview")
    assert family(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) CriOS/129.0.6668.69 Mobile/15E148 Safari/604.1"
    ) == ("ios", "chrome")
    assert family(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    ) == ("ios", "safari")
    assert family(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    ) == ("windows", "edge")
    assert family(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0"
    ) == ("macos", "firefox")
    assert parse_user_agent(None) == {
        "os": None,
        "os_version": None,
        "browser": None,
        "browser_version": None,
    }
