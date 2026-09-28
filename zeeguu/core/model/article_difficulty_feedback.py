from datetime import datetime

import zeeguu.core
from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model import Article, User
from zeeguu.core.model.db import db

DIFFICULTY_FEEDBACK = {
    "Too Easy": 1,
    "Ok": 3,
    "Too Hard": 5,
}


class ArticleDifficultyFeedback(db.Model):
    """

    Tuple (article, usr, feedback, date)
    Used for dificulty estimation

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    date = Column(DateTime)

    difficulty_feedback = Column(Integer)

    def __init__(self, user, article, difficulty_feedback=None):
        self.user = user
        self.article = article
        self.date = datetime.now()
        self.difficulty_feedback = difficulty_feedback

    def __repr__(self):
        return f"{self.user} and {self.article}: Feedback: {self.difficulty_feedback}, Date: {self.date}"

    @classmethod
    def find(cls, user: User, article: Article):
        try:
            return (
                cls.query.filter_by(user=user, article=article)
                .order_by(cls.date.desc())
                .first()
            )
        except NoResultFound:
            return None

    @classmethod
    def find_all_for_articles(cls, user: User, article_ids):
        """{article_id: most recent feedback} for one user in a single query."""
        if not article_ids:
            return {}
        rows = (
            cls.query.filter(cls.user_id == user.id, cls.article_id.in_(article_ids))
            .order_by(cls.date.asc())
            .all()
        )
        # ascending, so the last write per article wins -- same row find() picks
        return {r.article_id: r for r in rows}

    @classmethod
    def find_or_create(
        cls, session, user: User, article: Article, date: datetime, difficulty
    ):
        try:
            return cls.query.filter_by(user=user, article=article, date=date).one()
        except NoResultFound:
            print("creating new article difficulty feedback")
            try:
                new = cls(user, article, difficulty)
                session.add(new)
                session.commit()
                return new
            except Exception as e:
                from sentry_sdk import capture_exception

                capture_exception(e)
                print("seems we avoided a race condition")
                session.rollback()
                return cls.query.filter_by(user=user, article=article).one()
