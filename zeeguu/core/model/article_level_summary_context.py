from zeeguu.core.model.db import db
import sqlalchemy


class ArticleLevelSummaryContext(db.Model):
    """
    A context that is found in a per-level preview summary of an Article
    (see ArticleLevelSummary). Anchors a bookmark to a SPECIFIC level's summary
    so past-bookmark highlighting lands on the right tokens — summaries differ
    by level, so token coordinates are not shared across levels.

    Mirrors ArticleFragmentContext (keyed on a granular id, not article_id).
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    from zeeguu.core.model.bookmark import Bookmark

    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)
    bookmark = db.relationship(Bookmark)

    from zeeguu.core.model.article_level_summary import ArticleLevelSummary

    article_level_summary_id = db.Column(
        db.Integer, db.ForeignKey(ArticleLevelSummary.id)
    )
    article_level_summary = db.relationship(ArticleLevelSummary)

    def __init__(self, bookmark, article_level_summary):
        self.bookmark = bookmark
        self.article_level_summary = article_level_summary

    def __repr__(self):
        return f"<ArticleLevelSummaryContext als:{self.article_level_summary_id}, b:{self.bookmark_id}>"

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(cls, session, bookmark, article_level_summary, commit=True):
        try:
            return cls.query.filter(
                cls.bookmark == bookmark,
                cls.article_level_summary == article_level_summary,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(bookmark, article_level_summary)
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_article_level_summary(
        cls, user_id: int, article_level_summary_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model import Bookmark, UserWord

        result = (
            Bookmark.query.join(cls)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(cls.article_level_summary_id == article_level_summary_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]
