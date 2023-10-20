import sqlalchemy
from sqlalchemy import Column, String
from sqlalchemy.orm.exc import NoResultFound
from datetime import time

from zeeguu.core.model import User

from zeeguu.logging import log, logp

import zeeguu

from zeeguu.core.model import db


class UserPreference(db.Model):
    """
    All preferences are saved in the DB as user_id - key - value triples.
    Where the key and value are both Strings.

    To avoid working with hardcoded strings add the constant for the keys
    in this class, like DIFFICULTY_ESTIMATOR for example.

    Better yet, add also corresponding set and get methods, like:
        set_difficulty_estimator
        get_difficulty_estimator

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    key = Column(String(255), nullable=True)
    value = Column(String(255), nullable=True)

    # Key Names Below
    DIFFICULTY_ESTIMATOR = "difficulty_estimator"
    AUDIO_EXERCISES = "audio_exercises"

    def __init__(self, user: User, key=None, value=None):
        self.user = user
        self.key = key
        self.value = value

    def set(self, value: str):
        self.key = value

    def get(self):
        return self.value

    def __str__(self):
        return (
            f'Preferences (uid: {self.user_id}, key:"{self.key}", value:"{self.value}")'
        )

    # Specific Getter / Setter Methods below
    # --------------------------------------

    @classmethod
    def get_difficulty_estimator(cls, user: User):
        return cls.get(user, cls.DIFFICULTY_ESTIMATOR)

    @classmethod
    def set_difficulty_estimator(cls, session, user: User, key: value):
        return cls.set(session, user, cls.DIFFICULTY_ESTIMATOR, key)

    # Generic preference handling
    # ---------------------------

    @classmethod
    def _find(cls, user: User, key: str):
        return cls.query.filter_by(user=user, key=key).one()

    @classmethod
    def all_for_user(cls, user: User):
        all_preferences = cls.query.filter_by(user=user).all()
        return all_preferences

    @classmethod
    def find(cls, user: User, key: str):
        """
        :return: A UserPreference object, or None if none was found
        """
        try:
            return cls._find(user, key)
        except NoResultFound:
            return None

    @classmethod
    def get(cls, user: User, key: str):
        """
        :return: the value of a preference or None if none was found
        """
        try:
            return cls._find(user, key).value
        except NoResultFound:
            return None

    @classmethod
    def set(cls, session, user: User, key: str, value: str):
        """

            Generic method for setting a preference value.

        :param session:
        :param user:
        :param key:
        :param value:
        :return:
        """
        pref = cls.find_or_create(session, user, key)
        pref.value = value
        session.add(pref)
        session.commit()

    @classmethod
    def find_or_create(cls, session, user: User, key: str, value: str = None):
        try:
            return cls._find(user, key)
        except NoResultFound:
            try:
                new_pref = cls(user, key, value)
                session.add(new_pref)
                session.commit()
                log("Created new preference since original was missing")
                return new_pref
            except sqlalchemy.exc.IntegrityError:
                for _ in range(10):
                    try:
                        session.rollback()
                        pref = cls._find(user, key)
                        log("Successfully avoided race condition. Nice! ")
                        return pref
                    except sqlalchemy.orm.exc.NoResultFound:
                        time.sleep(0.3)
                        continue
                    break
