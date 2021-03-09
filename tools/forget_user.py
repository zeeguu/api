#!/usr/bin/env python

"""

   Script that forgets the personal data of a given user

"""

import zeeguu_core
from faker import Faker
from zeeguu_core.model import User

import sys


def forget_user(user):
    old_email = user.email
    old_name = user.name

    fake = Faker()
    user.name = "Forgotten Learner"
    user.email = fake.email()

    session = zeeguu_core.db.session
    session.add(user)
    session.commit()

    print(f"Before: {old_name} / {old_email} \nAfter: {user.name} / {user.email}")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <email>")
        exit(-1)

    user = User.find(sys.argv[1])
    forget_user(user)
