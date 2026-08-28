import json

import sqlalchemy

from zeeguu.core.model.article import Article
from zeeguu.core.model.db import db

# CEFR levels, simplest → most complex. Used to pick the best available summary
# for a learner's level.
CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _parsed_tokens(value):
    """A db.JSON column round-trips as a list/dict, but rows written when the
    column held a JSON *string* still exist — accept both, and never raise."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return value


class ArticleLevelSummary(db.Model):
    """
    The CEFR-level-specific card text for an Article: a short summary and the
    headline that goes above it, used as the tappable preview on feed cards.

    On-demand simplification means the crawl no longer creates a simplified child
    article per level, so the level-appropriate text lives here directly instead
    of on child-article rows. There is at most one row per (article, cefr_level),
    for levels simpler than the article's own level; the article's own-level text
    stays on ``Article.summary`` / ``Article.title``.

    (The table kept its ``article_level_summary`` name when the title columns were
    added — renaming it would have churned the two context joins and every FK.)
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
    # The level's headline, and its token stream. Nullable on purpose: every row
    # written before per-level titles existed has none, and a level whose title
    # came back in the wrong language is dropped while its summary is kept — both
    # fall back to the article's own title.
    title = db.Column(db.UnicodeText)
    tokenized_title = db.Column(db.JSON)
    # First-class generator entity (model_name + prompt_version), same as
    # Article.simplification_ai_generator_id — not a raw model-name string.
    ai_generator_id = db.Column(db.Integer, db.ForeignKey("ai_generator.id"))
    ai_generator = db.relationship("AIGenerator", foreign_keys=[ai_generator_id])
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __init__(
        self,
        article,
        cefr_level,
        summary,
        tokenized_summary=None,
        ai_generator_id=None,
        title=None,
        tokenized_title=None,
    ):
        self.article = article
        self.cefr_level = cefr_level
        self.summary = summary
        self.tokenized_summary = tokenized_summary
        self.title = title
        self.tokenized_title = tokenized_title
        self.ai_generator_id = ai_generator_id

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
        ai_generator_id=None,
        commit=True,
        title=None,
        tokenized_title=None,
    ):
        try:
            existing = cls.query.filter(
                cls.article_id == article.id,
                cls.cefr_level == cefr_level,
            ).one()
            existing.summary = summary
            existing.tokenized_summary = tokenized_summary
            existing.title = title
            existing.tokenized_title = tokenized_title
            existing.ai_generator_id = ai_generator_id
            session.add(existing)
            if commit:
                session.commit()
            return existing
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(
                article,
                cefr_level,
                summary,
                tokenized_summary,
                ai_generator_id,
                title,
                tokenized_title,
            )
            session.add(new)
            if commit:
                session.commit()
            return new

    @staticmethod
    def allowed_levels(user_level: str):
        """CEFR levels at or below ``user_level`` (the levels a learner can read),
        or None if the level is unknown."""
        if user_level not in CEFR_ORDER:
            return None
        return set(CEFR_ORDER[: CEFR_ORDER.index(user_level) + 1])

    @staticmethod
    def pick_best(candidates, user_level: str, article_own_level: str = None):
        """
        From ``candidates`` (any objects with a ``.cefr_level``), return the one at
        the highest level still at or below ``user_level``, or None. This is the
        single source of truth for level selection, shared by the single-article
        lookup and the batched feed overlay so they can't drift apart.

        ``article_own_level`` is the article's own CEFR level, and a learner at or
        above it gets None — meaning "use the article's own summary". Rows exist
        only for levels BELOW the article's own, so without this the highest
        *stored* row wins and every learner from the article's level upwards
        collapses onto it: for a Danish B1 article (rows A1, A2) the A2 row was
        served to A2, B1, B2, C1 and C2 readers alike, so changing level changed
        nothing. Passing it None keeps the old highest-row-wins behaviour for
        callers that genuinely have no article level to compare against.
        """
        allowed = ArticleLevelSummary.allowed_levels(user_level)
        if not allowed:
            return None
        if (
            article_own_level in CEFR_ORDER
            and CEFR_ORDER.index(user_level) >= CEFR_ORDER.index(article_own_level)
        ):
            return None
        eligible = [c for c in candidates if c.cefr_level in allowed]
        if not eligible:
            return None
        return max(eligible, key=lambda c: CEFR_ORDER.index(c.cefr_level))

    @classmethod
    def best_for_user_level(cls, article_id: int, user_level: str, article_own_level: str = None):
        """
        Return the ArticleLevelSummary best matching a learner's CEFR level: the
        highest stored level that is still at or below ``user_level`` (rows only
        exist for levels below the article's own, so a learner at or above the
        article level gets None and the caller falls back to Article.summary).
        Returns None when there's no suitable per-level summary.

        Pass ``article_own_level`` for that at-or-above check to actually happen —
        see pick_best.
        """
        allowed = cls.allowed_levels(user_level)
        if not allowed:
            return None
        rows = cls.query.filter(
            cls.article_id == article_id, cls.cefr_level.in_(allowed)
        ).all()
        return cls.pick_best(rows, user_level, article_own_level)

    def get_tokenized_summary(self):
        """Parse the cached token stream, tolerating either JSON text or a dict."""
        return _parsed_tokens(self.tokenized_summary)

    def get_tokenized_title(self):
        """Same, for the level's headline. None when this row predates per-level
        titles or its title was dropped by the language check."""
        return _parsed_tokens(self.tokenized_title)
