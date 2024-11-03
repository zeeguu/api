#!/usr/bin/env python

"""

   Script that lists recent users

"""

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

from collections import defaultdict

cohort_student_map = defaultdict(list)

from zeeguu.core.model import User

for user_id in User.all_recent_user_ids():
    user = User.find_by_id(user_id)
    # print(f"{user.name} ({user.email})")
    for ucmap in user.cohorts:
        # print(f"{ucmap.cohort.name}")
        # print(f"{teacher.name}")
        cohort_student_map[ucmap.cohort].append(user.name)

    # print("")
for cohort, values in cohort_student_map.items():
    print(f"============================")
    print(f"{cohort.name} ({cohort.language.code if cohort.language else ''})")
    print(f"============================")

    for teacher in cohort.get_teachers():
        print(f"  {teacher.name} ({teacher.email})")
    for v in values:
        print("  - ", v)

    print(" ")
