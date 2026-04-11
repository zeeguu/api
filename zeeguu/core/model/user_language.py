import datetime

from MySQLdb import IntegrityError
import sqlalchemy
from sqlalchemy import Column, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship

from zeeguu.core.model import User
from zeeguu.core.util.time import user_local_today, to_user_local_date

import zeeguu.core

from zeeguu.core.model.db import db


class UserLanguage(db.Model):
    """

    A UserLanguage is the 'personalized' version
    of a language. It contains the data about the user
    with respect to the language. Most importantly it
    contains the declared level, inferred level,
    and if the user is reading news / doing exercises.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    from zeeguu.core.model.language import Language

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    declared_level_min = Column(Integer)
    declared_level_max = Column(Integer)

    inferred_level_min = Column(Integer)
    inferred_level_max = Column(Integer)

    reading_news = Column(Boolean)
    doing_exercises = Column(Boolean)

    cefr_level = Column(Integer)

    last_practiced = Column(DateTime, nullable=True)
    daily_streak = Column(Integer, default=0)

    @property
    def local_last_practiced(self):
        return to_user_local_date(self.user, self.last_practiced)

    @property
    def current_daily_streak(self):
        """Stored streak, zeroed out if not practiced today or yesterday."""
        last_practiced = self.local_last_practiced
        yesterday = user_local_today(self.user) - datetime.timedelta(days=1)

        if last_practiced is None:
            return 0

        if last_practiced < yesterday:
            return 0

        return self.daily_streak or 0

    def __init__(
        self,
        user,
        language,
        declared_level_min=0,
        declared_level_max=10,
        inferred_level_min=0,
        inferred_level_max=10,
        reading_news=False,
        doing_exercises=False,
        cefr_level=0,
    ):
        self.user = user
        self.language = language
        self.declared_level_min = declared_level_min
        self.declared_level_max = declared_level_max
        self.inferred_level_min = inferred_level_min
        self.inferred_level_max = inferred_level_max
        self.reading_news = reading_news
        self.doing_exercises = doing_exercises
        self.cefr_level = cefr_level

    def get(self):
        return self.value

    def __str__(self):
        return f'User language (uid: {self.user_id}, language:"{self.Language}")'

    @classmethod
    def find_or_create(cls, session, user, language):
        try:
            return (
                cls.query.filter(cls.user == user)
                .filter(cls.language == language)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound:

            try:
                new = cls(user, language)
                session.add(new)
                session.commit()
                return new
            except IntegrityError as err:
                # it seems that sometimes we end up with a race condition
                if "Duplicate entry" in str(err):
                    return (
                        cls.query.filter(cls.user == user)
                        .filter(cls.language == language)
                        .one()
                    )

                raise (err)

    @classmethod
    def with_language_id(cls, i, user):
        return cls.query.filter(cls.user == user).filter(cls.language_id == i).one()

    @classmethod
    def all_for_user(cls, user):
        user_main_learned_language = user.learned_language
        user_languages = [
            language_id.language
            for language_id in cls.query.filter(cls.user == user).all()
        ]

        if user_main_learned_language not in user_languages:
            user_languages.append(user_main_learned_language)

        return user_languages

    def update_streak_if_needed(self, session=None):
        """
        Update last_practiced timestamp and daily_streak counter for this language.
        Only updates once per day to minimize database writes.
        """
        today = user_local_today(self.user)
        last_local = self.local_last_practiced

        if last_local is None or last_local < today:
            if last_local is None:
                self.daily_streak = 1
            elif last_local == today - datetime.timedelta(days=1):
                self.daily_streak = (self.daily_streak or 0) + 1
            else:
                self.daily_streak = 1

            self.last_practiced = datetime.datetime.now()
            if session:
                session.add(self)
