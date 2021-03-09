from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from sqlalchemy import (
    Column,
    UniqueConstraint,
    Integer,
    ForeignKey,
    DateTime,
    Boolean,
    or_,
)
from sqlalchemy.orm import relationship

from zeeguu_core.constants import JSON_TIME_FORMAT
from zeeguu_core.model import Article, User


class UserArticle(zeeguu_core.db.Model):
    """

    A user and an article.
    It's simple.

    Did she open it?
    Did she like it?

    The kind of info that's in here.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    # Together an url_id and user_id are UNIQUE :)
    UniqueConstraint(article_id, user_id)

    # once an article has been opened, we display it
    # in a different way in the article list; we might
    # also, just as well not even show it anymore
    # we don't keep only the boolean here, since it is
    # more informative to have the time when opened;
    # could turn out to be useful for showing the
    # user reading history for example
    opened = Column(DateTime)

    # There's a star icon at the top of an article;
    # Reader can use it to mark the article in any way
    # they like.
    starred = Column(DateTime)

    # There's a button at the bottom of every article
    # this tracks the state of that button
    liked = Column(Boolean)

    def __init__(self, user, article, opened=None, starred=None, liked=None):
        self.user = user
        self.article = article
        self.opened = opened
        self.starred = starred
        self.liked = liked

    def __repr__(self):
        return f"{self.user} and {self.article}: Opened: {self.opened}, Starred: {self.starred}, Liked: {self.liked}"

    def user_info_as_string(self):
        return f"{self.user} Opened: {self.opened}, Starred: {self.starred}, Liked: {self.liked}"

    def set_starred(self, state=True):
        if state:
            self.starred = datetime.now()
        else:
            self.starred = None

    def set_opened(self, state=True):
        if state:
            self.opened = datetime.now()
        else:
            self.opened = None

    def set_liked(self, new_state=True):
        self.liked = new_state

    def last_interaction(self):
        """

            sometimes we want to order articles based
            on this

        :return:
        """
        if self.opened:
            return self.opened
        if self.starred:
            return self.starred
        return None

    @classmethod
    def find_by_article(cls, article: Article):
        try:
            return cls.query.filter_by(article=article).all()
        except NoResultFound:
            return None

    @classmethod
    def find(cls, user: User, article: Article):
        """

        create a new object and add it to the db if it's not already there
        otherwise retrieve the existing object and update

        """
        try:
            return cls.query.filter_by(user=user, article=article).one()
        except NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        user: User,
        article: Article,
        opened=None,
        liked=False,
        starred=None,
    ):
        """

        create a new object and add it to the db if it's not already there
        otherwise retrieve the existing object and update

        """
        try:
            return cls.query.filter_by(user=user, article=article).one()
        except NoResultFound:
            try:
                new = cls(user, article, opened=opened, liked=liked, starred=starred)
                session.add(new)
                session.commit()
                return new
            except Exception as e:
                from sentry_sdk import capture_exception

                capture_exception(e)
                print("seems we avoided a race condition")
                session.rollback()
                return cls.query.filter_by(user=user, article=article).one()

    @classmethod
    def all_starred_articles_of_user(cls, user):
        return (
            cls.query.filter_by(user=user).filter(UserArticle.starred.isnot(None)).all()
        )

    @classmethod
    def all_starred_or_liked_articles_of_user(cls, user, limit=30):
        return (
            cls.query.filter_by(user=user)
            .filter(
                or_(UserArticle.starred.isnot(None), UserArticle.liked.isnot(False))
            )
            .order_by(UserArticle.article_id.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def all_starred_articles_of_user_info(cls, user):

        """

            prepares info as it is promised by /get_starred_articles

        :param user:
        :return:
        """

        user_articles = cls.all_starred_articles_of_user(user)

        dicts = [
            dict(
                user_id=each.user.id,
                url=each.article.url.as_string(),
                title=each.article.title,
                language=each.article.language.code,
                starred_date=each.starred.strftime(JSON_TIME_FORMAT),
                starred=(each.starred is not None),
                liked=each.liked,
            )
            for each in user_articles
        ]

        return dicts

    @classmethod
    def all_starred_and_liked_articles_of_user_info(cls, user):

        """

            prepares info as it is promised by /get_starred_articles

        :param user:
        :return:
        """

        user_articles = cls.all_starred_or_liked_articles_of_user(user)

        return [
            cls.user_article_info(user, each.article, with_translations=False)
            for each in user_articles
            if each.last_interaction() is not None
        ]

    @classmethod
    def exists(cls, obj):
        try:
            cls.query.filter(cls.id == obj.id).one()
            return True
        except NoResultFound:
            return False

    @classmethod
    def user_article_info(
        cls, user: User, article: Article, with_content=False, with_translations=True
    ):

        from zeeguu_core.model import Bookmark

        # Initialize returned info with the default article info
        returned_info = article.article_info(with_content=with_content)

        user_article_info = UserArticle.find(user, article)

        if not user_article_info:
            returned_info["starred"] = False
            returned_info["opened"] = False
            returned_info["liked"] = None
            returned_info["translations"] = []

            return returned_info

        returned_info["starred"] = user_article_info.starred is not None
        returned_info["opened"] = user_article_info.opened is not None
        returned_info["liked"] = user_article_info.liked
        if user_article_info.starred:
            returned_info["starred_time"] = user_article_info.starred.strftime(
                JSON_TIME_FORMAT
            )

        if with_translations:
            translations = Bookmark.find_all_for_user_and_url(user, article.url)
            returned_info["translations"] = [
                each.serializable_dictionary() for each in translations
            ]

        return returned_info
