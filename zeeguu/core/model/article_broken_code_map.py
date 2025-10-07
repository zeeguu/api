from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.article import Article

import sqlalchemy

from zeeguu.core.model.db import db


class LowQualityTypes:
    TOO_SHORT = "TOO_SHORT"
    TOO_LONG = "TOO_LONG"
    HTML_PATTERN = "HTML_PATTERN"
    TEXT_PAYWALL_PATTERN = "PAYWALL_PATTERN"       # Detected by text pattern matching
    LLM_PAYWALL_PATTERN = "LLM_PAYWALL"            # Detected by LLM during simplification
    INCOMPLETE_PATTERN = "INCOMPLETE_PATTERN"
    LIVE_BLOG = "LIVE_BLOG"
    ML_PREDICTION = "ML_PREDICTION"
    LANGUAGE_DOES_NOT_MATCH_FEED = "LANGUAGE_DOES_NOT_MATCH_FEED"
    ADVERTORIAL_PATTERN = "ADVERTORIAL_PATTERN"    # Detected by URL/keyword patterns
    ADVERTORIAL_LLM = "ADVERTORIAL_LLM"            # Detected by LLM during simplification
    DISTURBING_CONTENT_PATTERN = "DISTURBING_CONTENT_PATTERN"  # Detected by keyword patterns
    DISTURBING_CONTENT_LLM = "DISTURBING_CONTENT_LLM"          # Detected by LLM during simplification
    USER_REPORTED = "USER_REPORTED"


class ArticleBrokenMap(db.Model):
    """
    When an article is set as broken, then we pass a reason on why it was marked
    as broken.
    """

    __tablename__ = "article_broken_code_map"

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id))
    article = relationship(Article)

    broken_code = db.Column(db.String(42))
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
