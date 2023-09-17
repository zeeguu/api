from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from zeeguu.core.model import User
import zeeguu.core

from zeeguu.core.model import db


class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    def __init__(self, user):
        self.user = user

    def get_cohorts(self):
        return TeacherCohortMap.get_cohorts_for(self.user)

    @classmethod
    def exists(cls, user):
        return len(cls.query.filter_by(user_id=user.id).all()) > 0

    @classmethod
    def from_user(cls, user):
        cohort_count_of_user = len(TeacherCohortMap.get_cohorts_for(user))
        if cohort_count_of_user > 0:
            return cls(user)
        else:
            return None
