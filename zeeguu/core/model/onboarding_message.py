import sqlalchemy
from sqlalchemy import Column, Integer

from zeeguu.core.model.db import db

class OnboardingMessage(db.Model):
    """
    OnboardingMessage reflects the different types of onbaording messages
    that the system is able to output.

    """
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    type = db.Column(db.String)

    TRANSLATE_MSG = 1
    UNSELECT_MSG = 2
    REVIEW_WORDS_MSG = 3
    PRACTICE_MSG = 4
    DAILY_EXERCISES_MSG = 5
    WORD_LEVELS_MSG = 6
    LISTENING_MSG = 7

    def __repr__(self):
        return f"<OnboardingMessage: {self.id} Type: {self.type}>"

    @classmethod
    def find(cls, type):
        try:
            onboardingMessage = cls.query.filter(cls.type == type).one()
            return onboardingMessage
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_by_id(cls, i):
        try:
            onboardingMessage = cls.query.filter(cls.id == i).one()
            return onboardingMessage
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None