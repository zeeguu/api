#!/usr/bin/env python

"""

   Script that goes through all the users in a DB
   and renames their names with random ones.

"""

import zeeguu.core
from zeeguu.core.model import (
    User,
    UserActivityData,
    Bookmark,
    UserArticle,
    UserReadingSession,
    UserExerciseSession,
)
from sys import argv

if len(argv) < 3:
    print("CALL: consolidate_accounts <primary_id> <secondary_id>")
    exit(-1)

PRIMARY_ID = argv[1]
SECONDARY_ID = argv[2]

tables_to_modify = [
    Bookmark,
    UserActivityData,
    UserArticle,
    UserReadingSession,
    UserExerciseSession,
]

primary_user = User.find_by_id(PRIMARY_ID)
secondary_user = User.find_by_id(SECONDARY_ID)

for each_table in tables_to_modify:

    primary_user_items = each_table.query.filter_by(user_id=primary_user.id).all()
    secondary_user_items = each_table.query.filter_by(user_id=secondary_user.id).all()

    print(each_table.__tablename__)
    print(f"= Primary User Before:{len(primary_user_items)}")
    print(f"= Secondary User Before:{len(secondary_user_items)}")

    for each in secondary_user_items:
        each.user = primary_user
        zeeguu.core.model.db.session.add(each)
    zeeguu.core.model.db.session.commit()

    primary_user_items = each_table.query.filter_by(user_id=primary_user.id).all()
    secondary_user_items = each_table.query.filter_by(user_id=secondary_user.id).all()

    print(f"= Primary User After:{len(primary_user_items)}")
    print(f"= Secondary User After:{len(secondary_user_items)}")

    print(" ")
