from zeeguu.core.model.db import db
import sqlalchemy


class LevelAdaptedArticleSummaryContext(db.Model):
    """
    A context that is found in a per-level preview summary of an Article
    (see LevelAdaptedArticleText). Anchors a bookmark to a SPECIFIC level's summary
    so past-bookmark highlighting lands on the right tokens — summaries differ
    by level, so token coordinates are not shared across levels.

    Mirrors ArticleFragmentContext (keyed on a granular id, not article_id).
    """

    __table_args__ = (
        # At most one context row per (bookmark, level summary) — see find_or_create.
        db.UniqueConstraint(
            "bookmark_id",
            "level_adapted_article_text_id",
            # Keeps its pre-rename name: RENAME TABLE carries index names across
            # unchanged, and renaming an index buys nothing.
            name="uq_alsc_bookmark_summary",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)

    from zeeguu.core.model.bookmark import Bookmark

    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)
    bookmark = db.relationship(Bookmark)

    from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText

    level_adapted_article_text_id = db.Column(
        db.Integer, db.ForeignKey(LevelAdaptedArticleText.id)
    )
    level_adapted_article_text = db.relationship(LevelAdaptedArticleText)

    def __init__(self, bookmark, level_adapted_article_text):
        self.bookmark = bookmark
        self.level_adapted_article_text = level_adapted_article_text

    def __repr__(self):
        return f"<LevelAdaptedArticleSummaryContext als:{self.level_adapted_article_text_id}, b:{self.bookmark_id}>"

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(cls, session, bookmark, level_adapted_article_text, commit=True):
        existing = cls.query.filter(
            cls.bookmark == bookmark,
            cls.level_adapted_article_text == level_adapted_article_text,
        ).one_or_none()
        if existing:
            return existing

        # Insert inside a SAVEPOINT so that if a concurrent request created the
        # same (bookmark, level summary) between our SELECT and INSERT, the unique
        # constraint fires and we roll back just this insert (not the caller's
        # whole transaction, which may still be uncommitted when commit=False) and
        # return the row the other request created.
        new = cls(bookmark, level_adapted_article_text)
        try:
            with session.begin_nested():
                session.add(new)
        except sqlalchemy.exc.IntegrityError:
            return cls.query.filter(
                cls.bookmark == bookmark,
                cls.level_adapted_article_text == level_adapted_article_text,
            ).one()

        if commit:
            session.commit()
        return new

    @classmethod
    def get_all_user_bookmarks_for_level_adapted_summary(
        cls, user_id: int, level_adapted_article_text_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model import Bookmark, UserWord

        result = (
            Bookmark.query.join(cls)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(cls.level_adapted_article_text_id == level_adapted_article_text_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]
