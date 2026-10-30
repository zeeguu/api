import datetime

from fixtures import LoggedInClient, logged_in_client as client
from zeeguu.core.model import User, UserLanguage
from zeeguu.core.model.db import db
from zeeguu.core.util.time import server_now


def _streaks_by_code(client: LoggedInClient):
    return {each["code"]: each for each in client.get("/all_language_streaks")}


def test_last_practiced_date_is_the_users_local_day(client: LoggedInClient):
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = server_now() - datetime.timedelta(days=3)
    db.session.commit()

    entry = _streaks_by_code(client)[user.learned_language.code]

    assert entry["last_practiced_date"] == ul.local_last_practiced.isoformat()
    assert "T" not in entry["last_practiced_date"]


def test_last_practiced_date_is_null_for_a_language_never_practiced(client: LoggedInClient):
    user = User.find(client.email)
    ul = UserLanguage.find_or_create(db.session, user, user.learned_language)
    ul.last_practiced = None
    db.session.commit()

    assert _streaks_by_code(client)[user.learned_language.code]["last_practiced_date"] is None
