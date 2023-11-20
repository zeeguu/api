from MySQLdb import IntegrityError
import sqlalchemy
from sqlalchemy import Column, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from zeeguu.core.model import User

import zeeguu.core

from zeeguu.core.model import db


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
