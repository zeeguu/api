from fixtures import logged_in_client as client
from zeeguu.core.model import User, UserBrowsingSession


def test_browsing_session_captures_language_at_start(client):
    """Streak attribution must survive a later learned_language toggle, so
    the session captures the user's language at creation time."""
    session_id = client.post("/browsing_session_start")["id"]

    session = UserBrowsingSession.find_by_id(session_id)
    user = User.find(client.email)
    assert session.language_id == user.learned_language_id
