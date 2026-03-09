from fixtures import LoggedInClient, logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article

def test_accept_friend_request_success(client: LoggedInClient):
	"""
	Test accepting a friend request returns friendship dict.
	"""
	from zeeguu.core.model import User
	# Create another user and send friend request
	user_data = dict(password="test", username="accept", learned_language="de")
	client.post(f"/add_user/{other_email}", data=user_data)
	sender_user = User.find(other_email)
	
	other_email = "accept@user.com"
	other_user = User.find(other_email)
	print(other_user)
	client.post("/send_friend_request", json={"receiver_id": other_user.id})
	# Accept as other user
	# Simulate login as other user

	other_client = LoggedInClient(client.client)
	response = other_client.post("/accept_friend_request", json={"sender_id": sender_user.id})
	assert isinstance(response, dict)
	assert "status" in response


def test_reject_friend_request_success(client: LoggedInClient):
	"""
	Test rejecting a friend request returns True or similar.
	"""
	other_email = "reject@user.com"
	user_data = dict(password="test", username="reject", learned_language="de")
	client.post(f"/add_user/{other_email}", data=user_data)
	from zeeguu.core.model import User
	other_user = User.find(other_email)
	client.post("/send_friend_request", json={"receiver_id": other_user.id})
	from zeeguu.api.test.fixtures import LoggedInClient
	other_client = LoggedInClient(client.client)
	response = other_client.post("/reject_friend_request", json={"sender_id": client.email})
	assert response is True or str(response) == "True" or "True" in str(response)

def test_delete_friend_request_success(client: LoggedInClient):
	"""
	Test deleting a friend request returns 'True' or similar.
	"""
	# Create another user and send friend request
	other_email = "delete@user.com"
	user_data = dict(password="test", username="delete", learned_language="de")
	client.post(f"/add_user/{other_email}", data=user_data)
	from zeeguu.core.model import User
	other_user = User.find(other_email)
	client.post("/send_friend_request", json={"receiver_id": other_user.id})
	response = client.post("/delete_friend_request", json={"receiver_id": other_user.id})
	assert "True" in str(response) or response is True


def test_delete_friend_request_invalid_receiver(client: LoggedInClient):
	"""
	Test deleting a friend request with invalid receiver returns error.
	"""
	response = client.post("/delete_friend_request", json={"receiver_id": 999999})
	assert "invalid data sender_id or/and receiver_id" in str(response)

def test_send_friend_request_success(client: LoggedInClient):
	"""
	Test sending a friend request to another user returns expected dict.
	"""
	# Create another user
	other_email = "other@user.com"
	user_data = dict(password="test", username="other", learned_language="de")
	client.client.post(f"/add_user/{other_email}", data=user_data)
	from zeeguu.core.model import User
	other_user = User.find(other_email)
	# Send friend request
	response = client.post("/send_friend_request", json={"receiver_id": other_user.id})
	assert isinstance(response, dict)
	assert response["sender"]["id"] == other_user.id or response["receiver"]["id"] == other_user.id


def test_send_friend_request_to_self(client):
	"""
	Test sending a friend request to self returns error.
	"""
	from zeeguu.core.model import User
	user = User.find(client.email)
	response = client.post("/send_friend_request", json={"receiver_id": user.id})
	assert b"cannot send friend request to yourself" in response or "cannot send friend request to yourself" in str(response)
def test_get_friend_requests(client):
	"""
	Test the /get_friend_requests endpoint returns a list (empty or not).
	"""
	response = client.get("/get_friend_requests")
	assert isinstance(response, list)


def test_get_pending_friend_requests(client):
	"""
	Test the /get_pending_friend_requests endpoint returns a list (empty or not).
	"""
	response = client.get("/get_pending_friend_requests")
	assert isinstance(response, list)

def test_unfriend_success(client: LoggedInClient):
	"""
	Test unfriending removes friendship.
	"""
	other_email = "unfriend@user.com"
	user_data = dict(password="test", username="unfriend", learned_language="de")
	client.post(f"/add_user/{other_email}", data=user_data)
	from zeeguu.core.model import User
	other_user = User.find(other_email)
	client.post("/send_friend_request", json={"receiver_id": other_user.id})
	from zeeguu.api.test.fixtures import LoggedInClient
	other_client = LoggedInClient(client.client)
	other_client.post("/accept_friend_request", json={"sender_id": client.email})
	response = client.post("/unfriend", json={"receiver_id": other_user.id})
	assert response is True or str(response) == "True" or "True" in str(response)


def test_discover_friends(client):
	"""
	Test discover_friends returns a list.
	"""
	response = client.get("/discover_friends/test")
	assert isinstance(response, list)


def test_search_users(client):
	"""
	Test search_users returns a list.
	"""
	response = client.get("/search_users/test")
	assert isinstance(response, list)
import pytest
from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article


def test_get_friends(client):
	"""
	Test the /get_friends endpoint returns a list (empty or not).
	"""
	response = client.get("/get_friends")
	assert isinstance(response, list)

