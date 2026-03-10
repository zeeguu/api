from fixtures import LoggedInClient, logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article
from zeeguu.core.model import User
import json

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
	fr_response = client.post("/send_friend_request", json={"receiver_id": other_user.id})
	assert fr_response["friend_request_status"] == "pending"
	
	# User other client to accept friend request
	accept_fr_response = other_client.post("/accept_friend_request", json={"sender_id": sender_user.id})
	print(accept_fr_response)
	assert accept_fr_response["friend_request_status"] == "accepted"	


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
    client.post("/send_friend_request", json={"receiver_id": other_user.id}) 
    response = other_client.post("/reject_friend_request", json={"sender_id": sender_user.id})
    
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
	client.post("/send_friend_request", json={"receiver_id": other_user.id})
	response = client.post("/delete_friend_request", json={"receiver_id": other_user.id})
	assert "True" in str(response) or response is True


def test_delete_friend_request_invalid_receiver(client: LoggedInClient):
	"""
	Test deleting a friend request with invalid receiver returns error.
	"""
	response = client.post("/delete_friend_request", json={"receiver_id": 999999})
	assert response.get("success") is False

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
	response = client.post("/send_friend_request", json={"receiver_id": other_user.id})
	assert isinstance(response, dict)
	assert response["sender"]["id"] == other_user.id or response["receiver"]["id"] == other_user.id


def test_send_friend_request_to_self(client: LoggedInClient):
	"""
	Test sending a friend request to self returns error.
	"""
	from zeeguu.core.model import User
	user = User.find(client.email)
	response = client.post("/send_friend_request", json={"receiver_id": user.id})
	assert b"cannot send friend request to yourself" in response or "cannot send friend request to yourself" in str(response)

def test_get_friend_requests(client: LoggedInClient):
	"""
	Test the /get_friend_requests endpoint returns a list (empty or not).
	"""
	response = client.get("/get_friend_requests")
	assert isinstance(response, list)


def test_get_pending_friend_requests(client: LoggedInClient):
	"""
	Test the /get_pending_friend_requests endpoint returns a list (empty or not).
	"""
	response = client.get("/get_pending_friend_requests")
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
    client.post("/send_friend_request", json={"receiver_id": other_user.id})
    other_client.post("/accept_friend_request", json={"sender_id": sender_user.id})
    
    # Act: Unfirend
    response = client.post("/unfriend", json={"receiver_id": other_user.id})
    
    # Assert
    assert response.get("success") is True


def test_discover_friends(client: LoggedInClient):
	"""
	Test discover_friends returns a list.
	"""
	response = client.get("/discover_friends/test")
	assert isinstance(response, list)


def test_search_users(client: LoggedInClient):
	"""
	Test search_users returns a list.
	"""
	response = client.get("/search_users/test")
	assert isinstance(response, list)

def test_get_friends(client: LoggedInClient):
	"""
	Test the /get_friends endpoint returns a list (empty or not).
	"""
	response = client.get("/get_friends")
	assert isinstance(response, list)

