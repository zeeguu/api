#!/usr/bin/env python

"""

   Script that lists recent users

"""

DAYS_SINCE_ACTIVE = 30
SHOW_TEACHER_NAMES = True
SHOW_STUDENT_NAMES = True

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

from collections import defaultdict

cohort_student_map = defaultdict(list)

from zeeguu.core.model.user import User

for user_id in User.all_recent_user_ids(DAYS_SINCE_ACTIVE):
    user = User.find_by_id(user_id)
    # print(f"{user.name} ({user.email})")
    for ucmap in user.cohorts:
        # print(f"{ucmap.cohort.name}")
        # print(f"{teacher.name}")
        cohort_student_map[ucmap.cohort].append(user.name)

    # print("")

ordered_cohorts = sorted(
    cohort_student_map.keys(), key=lambda x: len(cohort_student_map[x]), reverse=True
)

print(f"Users active in the last {DAYS_SINCE_ACTIVE} days")
total_users = 0
for cohort in ordered_cohorts:
    values = cohort_student_map[cohort]
    print("")
    print(f"========================================================")
    print(
        f"{cohort.name} ({cohort.id}) "
        f"\nLang: {cohort.language.name if cohort.language else ''} "
        f"\nCode: {cohort.inv_code} "
    )

    if SHOW_TEACHER_NAMES:
        print("\nTeachers: ")
    for teacher in cohort.get_teachers():
        if SHOW_TEACHER_NAMES:
            print(f"  -  {teacher.name} ({teacher.email})")
    if SHOW_TEACHER_NAMES:
        print("")

    print(f"Active Students: {len(values)}")

    for v in values:
        total_users += 1
        if SHOW_STUDENT_NAMES:
            print("  - ", v)

    print(" ")

print("Total users: ", total_users)
