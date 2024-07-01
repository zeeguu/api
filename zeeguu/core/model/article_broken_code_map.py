from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.article import Article

import sqlalchemy

from zeeguu.core.model import db


class LowQualityTypes:
    TOO_SHORT = "TOO_SHORT"
    HTML_PATTERN = "HTML_PATTERN"
    TEXT_PAYWALL_PATTERN = "PAYWALL_PATTERN"
    INCOMPLETE_PATTERN = "INCOMPLETE_PATTERN"
    LIVE_BLOG = "LIVE_BLOG"
    ML_PREDICTION = "ML_PREDICTION"


class ArticleBrokenMap(db.Model):
    """
    When an article is set as broken, then we pass a reason on why it was marked
    as broken.
    """

    __tablename__ = "article_broken_code_map"

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id))
    article = relationship(Article)

    broken_code = db.Column(db.UnicodeText)
    __table_args__ = (
        PrimaryKeyConstraint(article_id, broken_code),
        {"mysql_collate": "utf8_bin"},
    )

    def __init__(self, article: Article, broken_code: LowQualityTypes):
        self.article = article
        self.broken_code = broken_code

    def __str__(self):
        return f"Article ({self.article_id}, broken: '{self.broken_code}')"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, article, broken_code):
        try:
            return (
                cls.query.filter(cls.article == article)
                .filter(cls.broken_code == broken_code)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(article, broken_code)
            session.add(new)
            session.commit()
            return new
