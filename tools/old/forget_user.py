#!/usr/bin/env python

"""

   Script that forgets the personal data of a given user

"""

import zeeguu.core
from faker import Faker
from zeeguu.core.model import User

import sys


def forget_user(user):
    old_email = user.email
    old_name = user.name

    fake = Faker()
    user.name = "Forgotten Learner"
    user.email = fake.email()

    db_session = zeeguu.core.model.db.session
    session.add(user)
    session.commit()

    print(f"Before: {old_name} / {old_email} \nAfter: {user.name} / {user.email}")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <email>")
        exit(-1)

    user = User.find(sys.argv[1])
    forget_user(user)
