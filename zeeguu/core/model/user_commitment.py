from sqlalchemy import Column, Integer
import sqlalchemy
from zeeguu.core.model import db


class UserCommitment(db.Model):
    """
    This class keeps track of the user's commitment.
    We can see how much time users choose to commit to on a weekly basis, and how many weeks they stick to their commitment.
    So we can study how much time, when and which articles the user has read.
    """

    __table_args__ = dict(mysql_collate="utf8_bin")
    __tablename__ = "user_commitment"

    user_minutes = db.Column(db.Integer)
    user_days = db.Column(db.Integer)
    consecutive_weeks = db.Column( db.Integer)
    id = db.Column(db.Integer)