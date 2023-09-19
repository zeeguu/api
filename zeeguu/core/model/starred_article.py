from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound

from sqlalchemy import (
    Column,
    UniqueConstraint,
    Integer,
    ForeignKey,
    String,
    DateTime,

)
from sqlalchemy.orm import relationship

from zeeguu.core.constants import SIMPLE_TIME_FORMAT
from zeeguu.core.model import Url, User
from zeeguu.core.model.language import Language
from zeeguu.core.model import db


class StarredArticle(db.Model):
    """

    This keeps track of information regarding a user's starred articles.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    url_id = Column(Integer, ForeignKey(Url.id))
    url = relationship(Url)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    title = Column(String(255))

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    # Useful for ordering past read articles
    starred_date = Column(DateTime)

    # Together an url_id and user_id identify an article
    UniqueConstraint(url_id, user_id)

    def __init__(self, user, url, _title: str, language):
        self.user = user
        self.url = url
        self.title = _title
        self.language = language
        self.starred_date = datetime.now()

    def __repr__(self):
        return f"{self.user} has starred: {self.title}"

    def as_dict(self):
        return dict(
            user_id=self.user_id,
            url=self.url.as_string(),
            title=self.title,
            language=self.language.code,
            starred_date=self.starred_date.strftime(SIMPLE_TIME_FORMAT),
        )

    @classmethod
    def find_or_create(cls, session, user: User, _url, _title: str, _language):
        """

                    create a new object and add it to the db if it's not already there
                    otherwise retrieve the existing object and update

                    in case of creation, the created object is incomplete

        \ """

        language = Language.find(_language)
        url = Url.find_or_create(session, _url, _title)

        try:
            return cls.query.filter_by(user=user, url=url).one()
        except NoResultFound:
            try:
                new = cls(user, url, _title, language)
                session.add(new)
                session.commit()
                return new
            except Exception as e:
                from sentry_sdk import capture_exception

                capture_exception(e)
                print("seems we avoided a race condition")
                session.rollback()
                return cls.query.filter_by(user=user, url=url).one()

    @classmethod
    def delete(cls, session, user, _url):

        try:
            url = Url.find(_url)
            item = cls.query.filter_by(user=user, url=url).one()
            session.delete(item)
            session.commit()
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)

    @classmethod
    def all_for_user(cls, user):
        return cls.query.filter_by(user=user).all()
