#!/usr/bin/env python

"""

   Script that lists recent users

"""

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

from collections import defaultdict

teacher_student_map = defaultdict(list)

from zeeguu.core.model import User

for user_id in User.all_recent_user_ids():
    user = User.find_by_id(user_id)
    # print(f"{user.name} ({user.email})")
    for ucmap in user.cohorts:
        # print(f"{ucmap.cohort.name}")
        for teacher in ucmap.cohort.get_teachers():
            # print(f"{teacher.name}")
            teacher_student_map[teacher].append(user.name)

    # print("")
for key, values in teacher_student_map.items():
    for v in values:
        print(key.email, " : ", v)
