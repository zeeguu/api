#!/usr/bin/env python

"""

   Script that lists recent users

   To be called from a cron job.

"""
import zeeguu.core
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap
from zeeguu.core.model.user import User

db_session = zeeguu.core.model.db.session
big_teacher = User.query.filter_by(id=534).one()

for cohort in Cohort.query.all():
    mapping = TeacherCohortMap.find_or_create(big_teacher, cohort, db_session)
    db_session.add(mapping)

db_session.commit()
