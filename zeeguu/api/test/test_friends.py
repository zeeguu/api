from fixtures import LoggedInClient, logged_in_client as client
from zeeguu.core.model import User
from zeeguu.core.model.friendship import Friendship


def test_accept_friend_request_success(client: LoggedInClient):
    """
    Test accepting a friend request returns friendship dict.
    """
    # Create another user and send friend request
    other_email = "accept@user.com"
    other_client = LoggedInClient(client.client,
                               email=other_email,
                               password="test",
                               username="accept",
                               learned_language="de")
    
    # Get users
    sender_user = User.find(client.email)
    other_user = User.find(other_email)

    # Send friend request
    fr_response = client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    assert not Friendship.are_friends(sender_user.id, other_user.id)

    # User other client to accept friend request
    accept_fr_response = other_client.post(
        "/accept_friend_request", json={"sender_username": sender_user.username}
    )
    assert Friendship.are_friends(sender_user.id, other_user.id)


def test_reject_friend_request_success(client: LoggedInClient):
    """
    Test rejecting a friend request returns success message.
    """
    other_email = "reject@user.com"
    other_client = LoggedInClient(client.client,
                                  email=other_email,
                                  password="test",
                                  username="reject",
                                  learned_language="de")
    
    # Find users and ids
    other_user = User.find(other_email)
    sender_user = User.find(client.email)
    
    # Act: Send friend request and reject it
    client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    response = other_client.post(
        "/reject_friend_request", json={"sender_username": sender_user.username}
    )
    
    # Assert
    assert response.get("success") is True

def test_delete_friend_request_success(client: LoggedInClient):
    """
    Test deleting a friend request returns 'True' or similar.
    """
    # Create another user and send friend request
    other_email = "delete@user.com"
    user_data = dict(password="test", username="delete", learned_language="de")
    client.post(f"/add_user/{other_email}", data=user_data)

    other_user = User.find(other_email)
    client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    response = client.post(
        "/delete_friend_request", json={"receiver_username": other_user.username}
    )
    assert response.get("success") is True


def test_delete_friend_request_invalid_receiver(client: LoggedInClient):
    """
    Test deleting a friend request with invalid receiver returns error.
    """
    response = client.response_from_post(
        "/delete_friend_request", json={"receiver_username": "missing_user"}
    )

    assert response.status_code == 404  
    assert response.get_json()["message"] == "User not found"
    

def test_send_friend_request_success(client: LoggedInClient):
    """
    Test sending a friend request to another user returns expected dict.
    """
    # Create another user
    other_email = "other@user.com"
    user_data = dict(password="test", username="other", learned_language="de")
    client.post(f"/add_user/{other_email}", data=user_data)
    from zeeguu.core.model import User
    other_user = User.find(other_email)
    # Send friend request
    sender_user = User.find(client.email)

    response = client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    assert isinstance(response, dict)
    assert response["sender"]["username"] == sender_user.username
    assert response["receiver"]["username"] == other_user.username


def test_send_friend_request_to_self(client: LoggedInClient):
    """
    Test sending a friend request to self returns error.
    """
    from zeeguu.core.model import User
    user = User.find(client.email)
    response = client.response_from_post(
            "/send_friend_request", json={"receiver_username": user.username}
        )
    assert response.status_code == 400
    assert response.get_json()["message"] == "cannot send friend request to yourself"

def test_get_friend_requests(client: LoggedInClient):
    """
    Test the /get_friend_requests endpoint returns a list (empty or not).
    """
    response = client.get("/get_sent_friend_requests")
    assert isinstance(response, list)


def test_get_pending_friend_requests(client: LoggedInClient):
    """
    Test the /get_pending_friend_requests endpoint returns a list (empty or not).
    """
    response = client.get("/get_received_friend_requests")
    assert isinstance(response, list)

def test_unfriend_success(client: LoggedInClient):
    other_email = "unfriend@user.com"
    other_client = LoggedInClient(client.client,
                                  email=other_email,
                                  password="test",
                                  username="unfriend",
                                  learned_language="de")
    sender_user = User.find(client.email)
    other_user = User.find(other_email)
    
    # Send and accept friend request
    client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    other_client.post(
        "/accept_friend_request", json={"sender_username": sender_user.username}
    )
    
    # Act: Unfirend
    response = client.post("/unfriend", json={"receiver_username": other_user.username})
    
    # Assert
    assert response.get("success") is True

def test_search_users(client: LoggedInClient):
    """
    Test search_users returns a list.
    """
    response = client.get("/search_users?query=test")
    assert isinstance(response, list)

def test_my_friends(client: LoggedInClient):
    """
    Test the /my_friends endpoint returns a list (empty or not).
    """
    response = client.get("/my_friends")
    assert isinstance(response, list)


def test_friends_of_for_friend_user_id(client: LoggedInClient):
    """
    Test /friends_of/<user_id> excludes the requester from the friend's friends list.
    """
    other_email = "friends-list@user.com"
    other_client = LoggedInClient(
        client.client,
        email=other_email,
        password="test",
        username="friends-list",
        learned_language="de",
    )
    third_email = "friends-list-third@user.com"
    third_client = LoggedInClient(
        client.client,
        email=third_email,
        password="test",
        username="friends-list-third",
        learned_language="de",
    )

    sender_user = User.find(client.email)
    other_user = User.find(other_email)
    third_user = User.find(third_email)

    client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    other_client.post(
        "/accept_friend_request", json={"sender_username": sender_user.username}
    )

    third_client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    other_client.post(
        "/accept_friend_request", json={"sender_username": third_user.username}
    )

    response = client.get(f"/friends_of/{other_user.username}")

    assert isinstance(response, list)
    friend_usernames = [entry["username"] for entry in response]
    assert sender_user.username in friend_usernames
    assert third_user.username in friend_usernames


def test_friends_of_for_non_friend_user_denied(client: LoggedInClient):
    """
    Test /friends_of/<user_id> denies access when users are not friends.
    """
    stranger_email = "friends-private@user.com"
    LoggedInClient(
        client.client,
        email=stranger_email,
        password="test",
        username="friends-private",
        learned_language="de",
    )
    stranger_user = User.find(stranger_email)

    response = client.get(f"/friends_of/{stranger_user.username}")

    assert isinstance(response, dict)
    assert response.get("message") == "You can only view friends of yourself or your friends."


def test_get_user_details_returns_current_user_data(client: LoggedInClient):
    """
    Test /get_user_details returns the logged-in user's details and feature flags.
    """
    user = User.find(client.email)

    response = client.get("/get_user_details")

    assert isinstance(response, dict)
    assert response["email"] == client.email
    assert response["name"] == user.name
    assert "learned_language" in response
    assert "native_language" in response
    assert "features" in response


def test_get_friend_details_returns_data_for_friend(client: LoggedInClient):
    """
    Test /get_friend_details/<friend_user_id> returns details when users are friends.
    """
    other_email = "friend-details@user.com"
    other_client = LoggedInClient(
        client.client,
        email=other_email,
        password="test",
        username="friend-details",
        learned_language="de",
    )

    sender_user = User.find(client.email)
    other_user = User.find(other_email)

    client.post(
        "/send_friend_request", json={"receiver_username": other_user.username}
    )
    other_client.post(
        "/accept_friend_request", json={"sender_username": sender_user.username}
    )

    response = client.get(f"/get_friend_details/{other_user.username}")

    assert isinstance(response, dict)
    assert response["name"] == other_user.name
    assert response["username"] == other_user.username
    assert "created_at" in response
    assert "user_avatar" in response
    assert "email" not in response
    assert "friendship" in response
    assert response["friendship"]["is_accepted"] == True
    assert isinstance(response["friendship"]["friend_streak"], int)


def test_get_friend_details_pending_request_shows_is_accepted_false(client: LoggedInClient):
    """
    Test /get_friend_details/<friend_user_id> shows friendship.is_accepted=False
    when a friend request has been sent but not yet accepted.
    """
    pending_email = "pending-details@user.com"
    LoggedInClient(
        client.client,
        email=pending_email,
        password="test",
        username="pending-details",
        learned_language="de",
    )
    pending_user = User.find(pending_email)

    client.post(
        "/send_friend_request", json={"receiver_username": pending_user.username}
    )

    response = client.get(f"/get_friend_details/{pending_user.username}")

    assert isinstance(response, dict)
    assert response["friendship"]["is_accepted"] == False


def test_get_friend_details_no_relationship_returns_none_friendship(client: LoggedInClient):
    """
    Test /get_friend_details/<friend_user_id> returns friendship=None when there is
    no friendship or friend request between the users.
    """
    stranger_email = "no-relation@user.com"
    LoggedInClient(
        client.client,
        email=stranger_email,
        password="test",
        username="no-relation",
        learned_language="de",
    )
    stranger_user = User.find(stranger_email)

    response = client.get(f"/get_friend_details/{stranger_user.username}")

    assert isinstance(response, dict)
    assert response.get("friendship") is None

