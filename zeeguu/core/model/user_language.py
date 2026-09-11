import datetime

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, UniqueConstraint
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

    # The unique index is named for the index production already has, so nobody
    # generates a second one. It is what find_or_create's duplicate-entry branch
    # exists for -- and, declared here, what stops the SQLite test database from
    # accepting pairs that MySQL would refuse.
    __table_args__ = (
        UniqueConstraint("user_id", "language_id", name="user_id"),
        {"mysql_collate": "utf8_bin"},
    )

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

    # The regional variety of this language the learner wants, as the ISO 3166-1
    # alpha-2 country it belongs to: ('nl', 'BE') is Flemish. NULL -- the default,
    # and what every existing row has -- means no preference, which has to keep
    # behaving exactly as it did before varieties existed.
    variety = Column(String(2))

    last_practiced = Column(DateTime, nullable=True)
    daily_streak = Column(Integer, default=0)
    max_streak = Column(Integer, default=0)
    max_streak_date = Column(DateTime, nullable=True)

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
    def variety_for(cls, user, language):
        """
        The regional variety this learner asked for in this language, or None.

        None is by far the common answer -- it is what every row held before
        varieties existed -- and it has to keep meaning "show me everything".
        """
        if user is None or language is None:
            return None
        row = cls.query.filter(cls.user == user).filter(cls.language == language).first()
        return row.variety if row else None

    @classmethod
    def find_or_create(cls, session, user, language):
        try:
            return (
                cls.query.filter(cls.user == user)
                .filter(cls.language == language)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound:
            # Two requests that both miss the query above both insert, and the
            # UNIQUE (user_id, language_id) lets exactly one of them through.
            #
            # The savepoint is what makes losing survivable. A failed flush leaves
            # the whole session needing a rollback before it can be used again --
            # so recovering without one raises PendingRollbackError, and
            # recovering with one throws away whatever the caller had pending,
            # answering 200 over changes that were never written. Rolling back to
            # a savepoint undoes this insert and nothing else.
            try:
                with session.begin_nested():
                    new = cls(user, language)
                    session.add(new)
                return new
            except sqlalchemy.exc.IntegrityError:
                return (
                    cls.query.filter(cls.user == user)
                    .filter(cls.language == language)
                    .one()
                )

    @classmethod
    def with_language_id(cls, i, user):
        return cls.query.filter(cls.user == user).filter(cls.language_id == i).one()

    @classmethod
    def all_languages_for_user(cls, user):
        user_main_learned_language = user.learned_language
        user_languages = [
            language_id.language
            for language_id in cls.query.filter(cls.user == user).all()
        ]

        if user_main_learned_language not in user_languages:
            user_languages.append(user_main_learned_language)

        return user_languages

    @classmethod
    def all_user_languages_for_user(cls, user, db_session):
        return db_session.query(cls).filter(cls.user == user).all()

    @classmethod
    def by_user_id_for_users(cls, user_ids):
        """
        Bulk variant of all_user_languages_for_user: one query for a whole list
        of users, returning {user_id: [UserLanguage, ...]}. Used when serializing
        a page of users (e.g. friend search results) to avoid a query per row.
        """
        if not user_ids:
            return {}

        result = {user_id: [] for user_id in user_ids}
        for user_language in db.session.query(cls).filter(cls.user_id.in_(user_ids)).all():
            result[user_language.user_id].append(user_language)

        return result

    def update_streak_if_needed(self, user, db_session):
        """
        Update last_practiced timestamp and daily_streak counter for this language.
        Only updates once per day to minimize database writes.
        """
        from zeeguu.core import events

        today = user_local_today(self.user)
        last_local = self.local_last_practiced

        if last_local is None or last_local < today:
            if last_local is None:
                self.daily_streak = 1
            elif last_local == today - datetime.timedelta(days=1):
                self.daily_streak = (self.daily_streak or 0) + 1
            else:
                # Gap in practice - save max before resetting
                self._update_max_streak_if_needed()
                self.daily_streak = 1

            self.last_practiced = datetime.datetime.now()
            self._update_max_streak_if_needed()

            db_session.add(self)
            db_session.flush()

            events.streak_changed.send(None, user_id=user.id, db_session=db_session)

            # Update friend streaks for all friendships
            events.friend_streak_changed.send(None, user_id=user.id, db_session=db_session)

    def _update_max_streak_if_needed(self):
        """Update max_streak if current streak exceeds it."""
        if self.daily_streak > (self.max_streak or 0):
            self.max_streak = self.daily_streak
            self.max_streak_date = self.last_practiced
