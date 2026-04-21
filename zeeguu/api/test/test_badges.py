from fixtures import LoggedInClient, logged_in_client as client
from zeeguu.core.model import User, db
from zeeguu.core.model.activity_type import ActivityType, ActivityMetric, BadgeType
from zeeguu.core.model.badge import Badge


def _create_test_activity_type():
    """Seed a minimal ActivityType with one Badge so the endpoint returns data."""
    at = ActivityType(
        metric=ActivityMetric.TRANSLATED_WORDS,
        name="Translated Words",
        badge_type=BadgeType.COUNTER,
    )
    db.session.add(at)
    db.session.flush()
    db.session.add(Badge(activity_type_id=at.id, level=1, threshold=50, name="Word Explorer", description="Translate {threshold} words while reading.", icon_name="/badge1.svg"))
    db.session.commit()


def test_get_badges_for_friend_user_id(client: LoggedInClient):
    """
    Test /badges/<username> returns badge data when users are friends.
    """
    _create_test_activity_type()

    other_email = "badges-friend@user.com"
    other_client = LoggedInClient(
        client.client,
        email=other_email,
        password="test",
        username="badges-friend",
        learned_language="de",
    )

    sender_user = User.find(client.email)
    other_user = User.find(other_email)

    client.post(
        "/send_friend_request",
        json={"receiver_username": other_user.username},
    )
    other_client.post(
        "/accept_friend_request",
        json={"sender_username": sender_user.username},
    )

    response = client.get(f"/badges/{other_user.username}")

    assert isinstance(response, list)
    assert len(response) > 0
    assert "name" in response[0]
    assert "badges" in response[0]


def test_get_badges_for_non_friend_user_denied(client: LoggedInClient):
    """
    Test /badges/<username> denies access when users are not friends.
    """
    stranger_email = "badges-private@user.com"
    LoggedInClient(
        client.client,
        email=stranger_email,
        password="test",
        username="badges-private",
        learned_language="de",
    )
    stranger_user = User.find(stranger_email)

    response = client.get(f"/badges/{stranger_user.username}")

    assert isinstance(response, dict)
    assert response.get("message") == "You can only view badges for yourself or your friends."
