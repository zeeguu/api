from fixtures import logged_in_client as client


def test_browsing_session_captures_language_at_start(client):
    """Streak attribution must survive a later learned_language toggle, so
    the session captures the user's language at creation time."""
    from zeeguu.core.model import UserBrowsingSession
    from zeeguu.core.model.language import Language

    session_id = client.post("/browsing_session_start")["id"]

    session = UserBrowsingSession.find_by_id(session_id)
    german = Language.find("de")  # the test fixture creates the user with learned_language="de"
    assert session.language_id == german.id
