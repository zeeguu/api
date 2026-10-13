from zeeguu.core.model.db import db
from sqlalchemy import Column, ForeignKey, func
from sqlalchemy.orm import relationship
from .cohort import Cohort
from .user import User


class UserCohortMap(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "user_cohort_map"
    user_id = Column(ForeignKey("user.id"), primary_key=True)
    cohort_id = Column(ForeignKey("cohort.id"), primary_key=True)
    user = relationship(User, back_populates="cohorts")
    cohort = relationship(Cohort, back_populates="users")

    @classmethod
    def last_member_activity_per_cohort(cls, cohort_ids):
        """{cohort_id: when one of its members was last seen}, in one query.

        last_seen is the account's, not the class's language: a student who
        is in a class is close enough to active in it. Cohorts with no members
        (or none ever seen) are absent from the map.
        """
        if not cohort_ids:
            return {}
        rows = (
            db.session.query(cls.cohort_id, func.max(User.last_seen))
            .join(User, User.id == cls.user_id)
            .filter(cls.cohort_id.in_(cohort_ids))
            .group_by(cls.cohort_id)
            .all()
        )
        return {cohort_id: last for cohort_id, last in rows if last is not None}
