from zeeguu.core.model.db import db
from sqlalchemy import Column, ForeignKey, func, or_
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
        """{cohort_id: when one of its students last practised the class's
        language}, in one query.

        UserLanguage.last_practiced, not User.last_seen: last_seen moves for
        anything an account does (a teacher in a teachers' class opening their
        own dashboard made it the "most active"). Developer accounts don't
        count. Day resolution: last_practiced is set on the first practice of
        a day. Cohorts with no such practice are absent from the map.
        """
        from zeeguu.core.model.user_language import UserLanguage

        if not cohort_ids:
            return {}
        rows = (
            db.session.query(cls.cohort_id, func.max(UserLanguage.last_practiced))
            .join(Cohort, Cohort.id == cls.cohort_id)
            .join(User, User.id == cls.user_id)
            .join(
                UserLanguage,
                (UserLanguage.user_id == cls.user_id)
                & (UserLanguage.language_id == Cohort.language_id),
            )
            .filter(cls.cohort_id.in_(cohort_ids))
            .filter(or_(User.is_dev.is_(None), User.is_dev == False))  # noqa: E712
            .group_by(cls.cohort_id)
            .all()
        )
        return {cohort_id: last for cohort_id, last in rows if last is not None}
