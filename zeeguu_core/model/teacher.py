from zeeguu_core.model.teacher_cohort_map import TeacherCohortMap
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from zeeguu_core.model import User
import zeeguu_core

db = zeeguu_core.db


class Teacher(zeeguu_core.db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    def __init__(self, user):
        self.user = user

    def get_cohorts(self):
        return TeacherCohortMap.get_cohorts_for(self.user)

    @classmethod
    def from_user(cls, user):
        cohort_count_of_user = len(TeacherCohortMap.get_cohorts_for(user))
        if cohort_count_of_user > 0:
            return cls(user)
        else:
            return None
