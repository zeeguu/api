#!/usr/bin/env python
import os
os.environ["PRELOAD_STANZA"] = "false"

"""

   Script that goes through all the users in a DB
   and replaces their names and emails with random ones.

"""

import sqlalchemy

import zeeguu.core
from faker import Faker
from zeeguu.api.app import create_app
from zeeguu.core.model import User

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

# Anonymize users
fake = Faker()

# Pre-compute one bcrypt hash and reuse for all users (much faster)
from werkzeug.security import generate_password_hash
ANON_PASSWORD_HASH = generate_password_hash("supersecret")

print("Anonymizing users...")
for user in User.query.all():
    for _ in range(0, 13):
        try:
            user.name = fake.name()
            user.email = fake.email()
            user.password = ANON_PASSWORD_HASH  # Use pre-computed hash
            db_session.add(user)
            db_session.commit()
            print(f"anonymized user id {user.id} to {user.name}")
            break
        except sqlalchemy.exc.IntegrityError as e:
            db_session.rollback()
            print(f"retrying...")
            continue
