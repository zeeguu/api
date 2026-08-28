from sqlalchemy import Column, Integer, Boolean, func
from sqlalchemy.orm import relationship
from sqlalchemy.sql import exists
from zeeguu.core.model.language import Language

from zeeguu.core.model.db import db


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

    # When set, students of this cohort see only the texts their teacher shares
    # with the class: no recommendation feed, no search, no shared inbox.
    only_classroom_texts = Column(Boolean, nullable=False, default=False)

    users = relationship("UserCohortMap", back_populates="cohort")

    def __init__(
        self,
        inv_code,
        name,
        language,
        max_students,
        level_min=0,
        level_max=10,
        only_classroom_texts=False,
    ):
        self.inv_code = inv_code
        self.name = name
        self.language = language
        self.max_students = max_students
        self.declared_level_min = level_min
        self.declared_level_max = level_max
        self.is_cohort_of_teachers = False  # by default a cohort is a student cohort!
        self.only_classroom_texts = only_classroom_texts

    def get_current_student_count(self):
        from zeeguu.core.model.user import User
        from zeeguu.core.model.user_cohort_map import UserCohortMap

        users_in_cohort = (
            User.query.join(UserCohortMap).filter_by(cohort_id=self.id).all()
        )
        return len(users_in_cohort)

    def cohort_still_has_capacity(self):
        # +10 here is just an approximation, because in the UI we
        # ask the teacher to give us an approximate number
        if self.get_current_student_count() < self.max_students + 10:
            return True
        return False

    def get_students(self):
        from zeeguu.core.model.user import User
        from zeeguu.core.model.user_cohort_map import UserCohortMap

        users = []
        if self.inv_code and len(self.inv_code) > 1:
            # adding those users that are only assigned based on
            # invitation code; this is for bacwards compatibility reasons
            users_in_UserCohortMap = exists().where(User.id == UserCohortMap.user_id)
            users.extend(
                User.query.filter_by(invitation_code=self.inv_code).filter(
                    ~users_in_UserCohortMap
                )
            )

        users.extend(
            User.query.join(UserCohortMap).filter(UserCohortMap.cohort == self).all()
        )

        return users

    def get_teachers(self):
        from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap

        return TeacherCohortMap.get_teachers_for(self)

    def get_cohort_info(self):
        return {
            "id": self.id,
            "name": self.name,
            "language_id": self.language_id,
        }

    def text_counts_by_language(self):
        """How many of this class's texts are in which language.

        Grouped by the *article's* language rather than the class's declared
        one, because that is what cohort_articles_for_user() filters on: a
        student sees a class text only when the article's language matches
        their learned language. The empty classroom uses these counts to say
        which language to switch to, so it has to count the same thing the
        filter counts.
        """
        from zeeguu.core.model.article import Article
        from zeeguu.core.model.cohort_article_map import CohortArticleMap

        rows = (
            db.session.query(Language, func.count(Article.id))
            .select_from(CohortArticleMap)
            .join(Article, Article.id == CohortArticleMap.article_id)
            .join(Language, Language.id == Article.language_id)
            .filter(CohortArticleMap.cohort_id == self.id)
            .group_by(Language.id)
            .all()
        )

        return [
            {"code": language.code, "name": language.name, "count": count}
            for language, count in sorted(rows, key=lambda each: -each[1])
        ]

    @classmethod
    def find(cls, id):
        return cls.query.filter_by(id=id).one()

    @classmethod
    def find_by_code(cls, invite_code):
        return cls.query.filter(func.lower(cls.inv_code) == invite_code.lower()).one()

    @classmethod
    def get_id(cls, inv):
        c = cls.query.filter(func.lower(cls.inv_code) == inv.lower()).one()
        return c.id

    @classmethod
    def exists_with_invite_code(cls, code: str):
        all_matching = cls.query.filter(func.lower(cls.inv_code) == code.lower()).all()
        return len(all_matching) > 0
