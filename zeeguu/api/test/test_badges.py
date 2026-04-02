from fixtures import LoggedInClient, logged_in_client as client
from zeeguu.core.model import User


def test_get_badges_for_friend_user_id(client: LoggedInClient):
    """
    Test /badges/<username> returns badge data when users are friends.
    """
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
    if response:
        assert "name" in response[0]
        assert "levels" in response[0]


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
