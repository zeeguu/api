from zeeguu.core.model import db
from sqlalchemy import Column, Integer, DateTime


class UserCommitment(db.Model):
    """
    This class keeps track of the user's commitment.
    We can see how much time users choose to commit to on a weekly basis, and how many weeks they stick to their commitment.
    So we can study how much time, when and which articles the user has read.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_commitment"

    id = Column(Integer, primary_key=True)
    user_minutes = Column(Integer)
    user_days = Column(Integer)
    consecutive_weeks = Column(Integer)
    commitment_last_updated = Column(DateTime)
    