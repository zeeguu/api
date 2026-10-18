import json

from fixtures import logged_in_client as client
from zeeguu.core.model import User
from zeeguu.core.model.db import db

# Names are free text via /user_settings, so the dashboards must not render them as HTML.
EVIL_NAME = '<script>alert("x")</script>'
EVIL_PERIOD = '"><script>alert(1)</script>'


def _make_admin_named(client, name):
    user = User.find(client.email)
    user.is_admin = True
    user.name = name
    db.session.commit()
    return user


def _html(client, url):
    response = client.client.get(client.append_session(url))
    assert response.status_code == 200
    return response, response.data.decode("utf-8")


def test_user_dashboard_escapes_the_user_name(client):
    user = _make_admin_named(client, EVIL_NAME)

    response, html = _html(client, f"/user_stats/user/{user.id}/dashboard")

    assert "<script>" not in html
    assert "&lt;script&gt;alert(&#34;x&#34;)&lt;/script&gt;" in html


def test_overview_dashboard_escapes_the_user_name(client):
    _make_admin_named(client, EVIL_NAME)
    client.post("/exercise_session_start")  # so the user shows up as active today

    response, html = _html(client, "/user_stats/dashboard?period=today")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_an_unknown_period_falls_back_to_the_default(client):
    user = _make_admin_named(client, "Admin")

    response, html = _html(client, f"/user_stats/user/{user.id}/dashboard?period={EVIL_PERIOD}")

    assert "<script>" not in html
    assert 'href="/user_stats/dashboard?period=yesterday"' in html

    stats = json.loads(client.client.get(client.append_session(f"/user_stats?period={EVIL_PERIOD}")).data)
    assert stats["period"]["name"] == "yesterday"


def test_admin_pages_forbid_scripts_and_framing(client):
    user = _make_admin_named(client, "Admin")

    response, _ = _html(client, f"/user_stats/user/{user.id}/dashboard")

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
