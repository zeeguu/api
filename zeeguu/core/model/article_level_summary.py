import json

import sqlalchemy

from zeeguu.core.model.article import Article
from zeeguu.core.model.db import db

# CEFR levels, simplest → most complex. Used to pick the best available summary
# for a learner's level.
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


class ArticleLevelSummary(db.Model):
    """
    A short, CEFR-level-specific summary of an Article, used as the tappable
    preview blurb on feed cards.

    On-demand simplification means the crawl no longer creates a simplified child
    article per level, so the level-appropriate summaries live here directly
    instead of on child-article rows. There is at most one row per
    (article, cefr_level), for levels simpler than the article's own level; the
    article's own-level summary stays on ``Article.summary``.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id), nullable=False)
    article = db.relationship(Article)

    cefr_level = db.Column(db.String(2), nullable=False)
    summary = db.Column(db.UnicodeText)
    # Cached token stream (same shape as ArticleTokenizationCache.tokenized_summary)
    # so the tappable preview renders without re-tokenizing on the request path.
    tokenized_summary = db.Column(db.JSON)
    ai_model = db.Column(db.String(255))
    created_at = db.Column(db.DateTime)

    def __init__(self, article, cefr_level, summary, tokenized_summary=None, ai_model=None):
        self.article = article
        self.cefr_level = cefr_level
        self.summary = summary
        self.tokenized_summary = tokenized_summary
        self.ai_model = ai_model

    def __repr__(self):
        return f"<ArticleLevelSummary a:{self.article_id} {self.cefr_level}>"

    @classmethod
    def find_by_id(cls, id: int):
        try:
            return cls.query.filter(cls.id == id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        article,
        cefr_level,
        summary,
        tokenized_summary=None,
        ai_model=None,
        commit=True,
    ):
        try:
            existing = cls.query.filter(
                cls.article_id == article.id,
                cls.cefr_level == cefr_level,
            ).one()
            existing.summary = summary
            existing.tokenized_summary = tokenized_summary
            existing.ai_model = ai_model
            session.add(existing)
            if commit:
                session.commit()
            return existing
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(article, cefr_level, summary, tokenized_summary, ai_model)
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def best_for_user_level(cls, article_id: int, user_level: str):
        """
        Return the ArticleLevelSummary best matching a learner's CEFR level: the
        highest stored level that is still at or below ``user_level`` (rows only
        exist for levels below the article's own, so a learner at or above the
        article level gets None and the caller falls back to Article.summary).
        Returns None when there's no suitable per-level summary.
        """
        if user_level not in CEFR_ORDER:
            return None
        allowed = set(CEFR_ORDER[: CEFR_ORDER.index(user_level) + 1])
        rows = cls.query.filter(cls.article_id == article_id).all()
        candidates = [r for r in rows if r.cefr_level in allowed]
        if not candidates:
            return None
        return max(candidates, key=lambda r: CEFR_ORDER.index(r.cefr_level))

    def get_tokenized_summary(self):
        """Parse the cached token stream, tolerating either JSON text or a dict."""
        if not self.tokenized_summary:
            return None
        if isinstance(self.tokenized_summary, str):
            try:
                return json.loads(self.tokenized_summary)
            except (ValueError, TypeError):
                return None
        return self.tokenized_summary
