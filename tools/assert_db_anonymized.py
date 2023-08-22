#!/usr/bin/env python

"""

   Script that goes through all the users in a DB
   and replaces their names and emails with random ones.

"""
from zeeguu.core.model import User

u = User.find_by_id(534)
print(u.email)

assert "mir.lu" not in u.email
