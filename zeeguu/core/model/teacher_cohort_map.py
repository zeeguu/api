from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model import User
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model import db


class TeacherCohortMap(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    cohort_id = Column(Integer, ForeignKey(Cohort.id))
    cohort = relationship(Cohort)

    def __init__(self, user, cohort):
        self.user = user
        self.cohort = cohort

    @classmethod
    def is_teacher(cls, user):
        return len(cls.query.filter_by(teacher=user).all()) > 0

    @classmethod
    def get_cohorts_for(cls, user):
        return [
            teacher_role.cohort for teacher_role in cls.query.filter_by(user=user).all()
        ]

    @classmethod
    def get_teachers_for(cls, cohort):
        return [
            teacher_role.user
            for teacher_role in cls.query.filter_by(cohort=cohort).all()
        ]

    @classmethod
    def find_or_create(cls, user, cohort, session):
        try:
            return cls.query.filter_by(user=user).filter_by(cohort=cohort).one()
        except NoResultFound as e:
            new = cls(user, cohort)
            session.add(new)
            session.commit()
            return new
