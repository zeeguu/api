from fixtures import LoggedInClient, logged_in_client as client
from zeeguu.core.model import User, db
from zeeguu.core.model.badge_category import BadgeCategory, ActivityMetric, AwardMechanism
from zeeguu.core.model.badge import Badge
from zeeguu.core.model.user_badge import UserBadge


def _create_test_badge_category():
    """Seed a minimal BadgeCategory with two Badge levels and return their IDs."""
    bc = BadgeCategory(
        metric=ActivityMetric.TRANSLATED_WORDS,
        name="Translated Words",
        award_mechanism=AwardMechanism.COUNTER
    )
    db.session.add(bc)
    db.session.flush()
    badge_1 = Badge(
        badge_category_id=bc.id,
        level=1,
        threshold=50,
        name="Word Explorer",
        unachieved_description="Translate 50 words while reading.",
        achieved_description="Translate 50 words while reading.",
        icon_name="/badge1.svg",
    )
    badge_2 = Badge(
        badge_category_id=bc.id,
        level=2,
        threshold=100,
        name="Word Master",
        unachieved_description="Translate 100 words while reading.",
        achieved_description="Translate 100 words while reading.",
        icon_name="/badge2.svg",
    )
    db.session.add(badge_1)
    db.session.add(badge_2)
    db.session.commit()
    return bc.id, badge_1.id, badge_2.id


def test_friend_badges_only_returns_achieved_badges_without_progress(client: LoggedInClient):
    """
    Test /friend_badges/<username> includes only achieved badges and no progress values.
    """
    _, badge_1_id, _ = _create_test_badge_category()

    other_email = "badges-friend-achieved@user.com"
    other_client = LoggedInClient(
        client.client,
        email=other_email,
        password="test",
        username="badges-friend-achieved",
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

    UserBadge.create(db.session, other_user.id, badge_1_id, is_shown=False)
    db.session.commit()

    response = client.get(f"/friend_badges/{other_user.username}")

    assert isinstance(response, list)
    assert len(response) == 1
    assert "name" in response[0]
    assert "badges" in response[0]
    assert "current_value" not in response[0]
    assert len(response[0]["badges"]) == 1
    assert response[0]["badges"][0]["achieved"] is True


def test_friend_badges_returns_empty_when_no_achieved(client: LoggedInClient):
    """
    Test /friend_badges/<username> returns no categories for friends with no achievements.
    """
    _create_test_badge_category()

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

    response = client.get(f"/friend_badges/{other_user.username}")

    assert isinstance(response, list)
    assert len(response) == 0


def test_friend_badges_for_non_friend_user_denied(client: LoggedInClient):
    """
    Test /friend_badges/<username> denies access when users are not friends.
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

    response = client.get(f"/friend_badges/{stranger_user.username}")

    assert isinstance(response, dict)
    assert response.get("message") == "You can only view badges for yourself or your friends."
