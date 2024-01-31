#!/usr/bin/env python

"""

   Script that goes through all the users in a DB
   and replaces their names and emails with random ones.

"""
import sqlalchemy

import zeeguu.core
from faker import Faker
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

fake = Faker()
from zeeguu.core.model import User

db_session = zeeguu.core.model.db.session

for user in User.query.all():
    for _ in range(0, 13):
        try:
            user.name = fake.name()
            user.email = fake.email()
            db_session.add(user)
            db_session.commit()
            print(f"anonymized user id {user.id} to {user.name}")
            break
        except sqlalchemy.exc.IntegrityError as e:
            db_session.rollback()
            print(f"retrying...")
            continue
