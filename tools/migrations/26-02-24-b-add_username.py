#!/usr/bin/env python
"""
Migration script to automatically populate usernames for existing users.

The usernames are generated in the format 'adjective_animal1234' (e.g., 'brave_tiger5678')
and are guaranteed to be unique across the user base.
A corresponding user avatar is also generated based on the animal in the username.
This script should be run after the database schema has been updated to include the new 'username' column in the 'user' table.

26-02-24-a-add_username.sql should have been run first to add the 'username' column to the 'user' table.

Run with: pip install -e . && python tools/migrations/26-02-24-b-add_username.py
"""
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.core.model.user import User


def populate_usernames():
    # Only query users who don't have a username set (i.e., those with username == None)
    users: list[User] = User.query.filter(User.username == None).all()
    for user in users:
        user.username = User.generate_unique_username()
        user_avatar = UserAvatar.create_default_avatar_for_user(user)
        db.session.add(user_avatar)
    db.session.commit()


if __name__ == "__main__":
    from zeeguu.api.app import create_app
    from zeeguu.core.model import db

    app = create_app()
    app.app_context().push()

    print("Starting random username population...")
    populate_usernames()
    print("Username population completed.")
