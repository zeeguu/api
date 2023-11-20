import zeeguu.core
from sqlalchemy import Column, Integer, Boolean
from sqlalchemy.orm import relationship
from zeeguu.core.model.language import Language

from zeeguu.core.model import db


class Cohort(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    inv_code = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(255))
    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    max_students = db.Column(db.Integer)
    language = relationship(Language, foreign_keys=[language_id])
    declared_level_min = Column(Integer)
    declared_level_max = Column(Integer)
    is_cohort_of_teachers = Column(Boolean)

    def __init__(
        self, inv_code, name, language, max_students, level_min=0, level_max=10
    ):
        self.inv_code = inv_code
        self.name = name
        self.language = language
        self.max_students = max_students
        self.declared_level_min = level_min
        self.declared_level_max = level_max
        self.is_cohort_of_teachers = False  # by default a cohort is a student cohort!

    def get_current_student_count(self):
        from zeeguu.core.model.user import User

        users_in_cohort = User.query.filter_by(cohort_id=self.id).all()
        return len(users_in_cohort)

    def cohort_still_has_capacity(self):
        # +10 here is just an approximation, because in the UI we
        # ask the teacher to give us an approximate number
        if self.get_current_student_count() < self.max_students + 10:
            return True
        return False

    def get_students(self):
        from zeeguu.core.model.user import User

        users = []
        if self.inv_code and len(self.inv_code) > 1:
            # adding those users that are only assigned based on
            # invitation code; this is for bacwards compatibility reasons
            users.extend(
                User.query.filter_by(
                    invitation_code=self.inv_code, cohort_id=None
                ).all()
            )

        users.extend(User.query.filter(User.cohort == self).all())

        return users

    def get_teachers(self):
        from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap

        return TeacherCohortMap.get_teachers_for(self)

    @classmethod
    def find(cls, id):
        return cls.query.filter_by(id=id).one()

    @classmethod
    def find_by_code(cls, invite_code):
        return cls.query.filter_by(inv_code=invite_code).one()

    @classmethod
    def get_id(cls, inv):
        c = cls.query.filter_by(inv_code=inv).one()
        return c.id

    @classmethod
    def exists_with_invite_code(cls, code: str):
        all_matching = cls.query.filter_by(inv_code=code).all()
        return len(all_matching) > 0
