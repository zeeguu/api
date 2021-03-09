#!/usr/bin/env python

"""

   Script that goes through all the users in a DB
   and replaces their names and emails with random ones.

"""
import sqlalchemy

import zeeguu_core
from faker import Faker
fake = Faker()
from zeeguu_core.model import User

session = zeeguu_core.db.session

for user in User.query.all():
    for _ in range(0,13):
        try:
            user.name = fake.name()
            user.email = fake.email()
            session.add(user)
            session.commit()
            print (f"anonimized user id {user.id} to {user.name}")
            break
        except sqlalchemy.exc.IntegrityError as e:
            session.rollback()
            print (f"retrying...")
            continue
