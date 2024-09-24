from zeeguu.core.model import db
from sqlalchemy import Column, ForeignKey
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
