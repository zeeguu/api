"""
Tests for onboarding message endpoints and model.
"""
import json
import pytest
from fixtures import logged_in_client as client
from zeeguu.core.model import UserOnboardingMessage, OnboardingMessage
from zeeguu.core.model.db import db


def test_get_onboarding_message_status_returns_false_when_not_shown(client):
    """Verify status endpoint returns false for messages that haven't been shown yet."""
    response = client.get("/get_onboarding_message_status?onboarding_message_id=1")
    assert response["shown"] is False


def test_get_onboarding_message_status_returns_true_after_marked_shown(client):
    """Verify status endpoint returns true after message is marked shown."""
    # Mark message as shown
    client.post("/mark_onboarding_message_shown", data={"onboarding_message_id": 1})
    
    # Check status
    response = client.get("/get_onboarding_message_status?onboarding_message_id=1")
    assert response["shown"] is True


def test_click_endpoint_refuses_cross_user_update(app, client):
    """Verify a user cannot click another user's message."""
    from fixtures import LoggedInClient
    
    # Create second user
    with app.test_client() as other_client:
        other_logged_in = LoggedInClient(
            other_client,
            email="other@mir.lu",
            username="other_user"
        )
    
    # User 1 marks message 2 as shown
    client.post("/mark_onboarding_message_shown", data={"onboarding_message_id": 2})
    
    # Verify user 1 has the message
    response = client.get("/get_onboarding_message_status?onboarding_message_id=2")
    assert response["shown"] is True
    
    # User 2 tries to click it via a direct DB manipulation attack
    response = other_logged_in.response_from_post(
        "/set_onboarding_message_click_time",
        data={"onboarding_message_id": 2}
    )
    assert response.status_code == 404  # User 2 doesn't have this message
    
    # Verify user 1's message is unchanged (no click time)
    from zeeguu.core.model import User
    user1 = User.find(client.email)
    user_msg = UserOnboardingMessage.find_by_user_and_message(user1.id, 2)
    assert user_msg.message_click_time is None


def test_find_or_create_idempotency(app):
    """Verify find_or_create returns the same row on repeated calls."""
    from zeeguu.core.model import User
    
    with app.app_context():
        # Create a test user
        user = User("test@idempotent.test", "Test User", "password", "test_user")
        db.session.add(user)
        db.session.commit()
        
        msg_id = 3
        
        # First call: creates the row
        record1 = UserOnboardingMessage.find_or_create_for_user_and_message(
            db.session, user.id, msg_id
        )
        db.session.commit()
        row_id_1 = record1.id
        
        # Second call: should find the existing row
        record2 = UserOnboardingMessage.find_or_create_for_user_and_message(
            db.session, user.id, msg_id
        )
        db.session.commit()
        row_id_2 = record2.id
        
        # Both should be the same
        assert row_id_1 == row_id_2
        
        # Verify there's exactly one row
        all_records = UserOnboardingMessage.query.filter_by(
            user_id=user.id,
            onboarding_message_id=msg_id
        ).all()
        assert len(all_records) == 1