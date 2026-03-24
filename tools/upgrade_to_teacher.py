#!/usr/bin/env python

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.user import User
from zeeguu.core.model.teacher import Teacher

email = input("User email: ")

user = User.find(email)
if not user:
    print(f"No user found with email: {email}")
    exit(1)

print(f"Found user: {user.name} (id={user.id})")

if Teacher.exists(user):
    print("User is already a teacher.")
    exit(0)

teacher = Teacher(user)
db.session.add(teacher)
db.session.commit()

print(f"User '{user.name}' has been upgraded to teacher.")
