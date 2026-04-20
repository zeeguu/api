#!/usr/bin/env python
"""
Migration script to automatically populate usernames for existing users.

The usernames are generated in the format 'adjective_animal1234' (e.g., 'brave_tiger5678')
and are guaranteed to be unique across the user base.
A corresponding user avatar is also generated based on the animal in the username.
This script should be run after the database schema has been updated to include the new 'username' column in the 'user' table.

26-02-24-a--add_username.sql should have been run first to add the 'username' column to the 'user' table.

Run with: pip install -e . && python tools/migrations/26-02-24-b--add_username.py

You might have to run this before: 
set -a 
source .env
set +a
to set the environment variables before running the script.
"""
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.core.model.user import User


def populate_usernames():
    # Only query users who don't have a username set (i.e., those with username == None)
    users: list[User] = User.query.filter(User.username.is_(None)).all()
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} Found {len(users)} users without usernames. Populating now...")
    for user in users:
        generated_username, animal = User.generate_unique_username()
        user.username = generated_username
        if UserAvatar.find(user.id) is None:
            db.session.add(UserAvatar(user.id, animal, None, None))
    db.session.commit()


if __name__ == "__main__":
    from zeeguu.api.app import create_app
    from zeeguu.core.model import db
    from datetime import datetime
    app = create_app()
    app.app_context().push()
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"{start_time} {'='*60}")
    print(f"{start_time} STARTING - username population...")
    populate_usernames()
    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"{end_time} COMPLETED - username population.")
    print(f"{end_time} {'='*60}")
