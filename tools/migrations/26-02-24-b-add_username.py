#!/usr/bin/env python
"""
Migration script to automatically populate usernames for existing users.

The usernames are generated in the format 'adjective_noun1234' (e.g., 'brave_tiger5678')
and are guaranteed to be unique across the user base. 
This script should be run after the database schema has been updated to include the new 'username' column in the 'users' table.

26-02-24-a-add_username.sql should have been run first to add the 'username' column to the 'user' table.

Run with: source ~/.venvs/z_env/bin/activate && python tools/migrations/26-02-24-b-add_username.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.core.model.user import User
from zeeguu.core.model import db

def generate_unique_username():

    while True:
        username = User.generate_username()
        exists = User.query.filter_by(username=username).first()
        if not exists:
            return username

def populate_usernames():
    users : list[User] = User.query.all()
    for user in users:
        user.username = generate_unique_username()
    db.session.commit()


if __name__ == "__main__":

    from zeeguu.api.app import create_app
    from zeeguu.core.model import db

    app = create_app()
    app.app_context().push()

    print("Starting random username population...")
    populate_usernames()
    print("Username population completed.")