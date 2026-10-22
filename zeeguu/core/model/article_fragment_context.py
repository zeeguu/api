from zeeguu.core.model.db import db
import sqlalchemy
from zeeguu.core.model.race_safe import find_or_create


class ArticleFragmentContext(db.Model):
    """
    A context that is found in a fragment of an Article.
    """

    __table_args__ = (
        # At most one context row per (bookmark, article fragment) — see find_or_create.
        db.UniqueConstraint(
            "bookmark_id",
            "article_fragment_id",
            name="uq_afc_bookmark_fragment",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)
    from zeeguu.core.model.bookmark import Bookmark

    bookmark_id = db.Column(
        db.Integer, db.ForeignKey(Bookmark.id, ondelete="CASCADE"), nullable=False
    )
    bookmark = db.relationship(Bookmark)

    from zeeguu.core.model.article_fragment import ArticleFragment

    article_fragment_id = db.Column(db.Integer, db.ForeignKey(ArticleFragment.id))
    article_fragment = db.relationship(ArticleFragment)

    def __init__(
        self,
        bookmark,
        article_fragment,
    ):
        self.bookmark = bookmark
        self.article_fragment = article_fragment

    def __repr__(self):
        return f"<ArticleFragmentContext a_fragment:{self.article_fragment_id}, b:{self.bookmark.id}>"

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(cls, session, bookmark, article_fragment, commit=True):
        return find_or_create(
            session,
            cls,
            dict(bookmark=bookmark, article_fragment=article_fragment),
            lambda: cls(bookmark, article_fragment),
            commit=commit,
        )

    @classmethod
    def get_all_user_bookmarks_for_article_fragment(
        cls, user_id: int, article_fragment_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model import Bookmark, UserWord

        result = (
            Bookmark.query.join(cls)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(cls.article_fragment_id == article_fragment_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]
