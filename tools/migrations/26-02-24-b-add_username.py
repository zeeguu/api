#!/usr/bin/env python
"""
Migration script to backfill reading_session_id on existing bookmarks.

For each bookmark without a reading_session_id, finds the reading session where:
- Same user
- Same article
- Bookmark creation time falls within the reading session's time window

Run with: source ~/.venvs/z_env/bin/activate && python tools/migrations/26-02-24-b-add_username.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.core.model.user import User
from zeeguu.core.model import db
import random

ADJECTIVES = [
    "brave", "clever", "curious", "silent", "rapid",
    "happy", "bright", "nordic", "bold", "calm"
]

NOUNS = [
    "otter", "falcon", "wolf", "learner",
    "linguist", "explorer", "reader", "thinker"
]


def generate_username():
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    number = random.randint(1, 999)

    return f"{adjective}_{noun}{number}"

def generate_unique_username():

    while True:
        username = generate_username()
        exists = User.query.filter_by(username=username).first()
        if not exists:
            return username

def populate_usernames():
    users = User.query.all()
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