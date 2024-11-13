#!/usr/bin/env python

"""

   Script that lists recent users

"""

DAYS_SINCE_ACTIVE = 30
SHOW_TEACHER_NAMES = False
SHOW_STUDENT_NAMES = False

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

from collections import defaultdict

cohort_student_map = defaultdict(list)

from zeeguu.core.model import User

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
for cohort in ordered_cohorts:
    values = cohort_student_map[cohort]
    print(f"========================================================")
    print(
        f"{cohort.name} ({cohort.id}) "
        f"\nLang: {cohort.language.code if cohort.language else ''} "
        f"\nInv Code: {cohort.inv_code} "
        f"\nActive Students: {len(values)}"
    )
    print(f"========================================================")

    for teacher in cohort.get_teachers():
        if SHOW_TEACHER_NAMES:
            print(f"  {teacher.name} ({teacher.email})")

    for v in values:
        if SHOW_STUDENT_NAMES:
            print("  - ", v)

    print(" ")
