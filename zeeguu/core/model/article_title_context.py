from zeeguu.core.model.article import Article
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
import sqlalchemy
from zeeguu.core.model.race_safe import find_or_create


class ArticleTitleContext(db.Model):
    """
    A context that is found in a title of an Article.
    """

    __table_args__ = (
        # At most one context row per (bookmark, article) title — see find_or_create.
        db.UniqueConstraint(
            "bookmark_id",
            "article_id",
            name="uq_atc_bookmark_article",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)
    bookmark_id = db.Column(
        db.Integer, db.ForeignKey(Bookmark.id, ondelete="CASCADE"), nullable=False
    )
    bookmark = db.relationship(Bookmark)

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id))
    article = db.relationship(Article)

    def __init__(
        self,
        bookmark,
        article,
    ):
        self.bookmark = bookmark
        self.article = article

    def __repr__(self):
        return f"<ArticleTitleContext b:{self.bookmark_id}, a:{self.article_id}>"

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        bookmark,
        article,
        commit=True,
    ):
        return find_or_create(
            session,
            cls,
            dict(bookmark=bookmark, article=article),
            lambda: cls(bookmark, article),
            commit=commit,
        )

    @classmethod
    def get_all_user_bookmarks_for_article_title(
        cls, user_id: int, article_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model.user_word import UserWord

        result = (
            Bookmark.query.join(ArticleTitleContext)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(ArticleTitleContext.article_id == article_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]

    @classmethod
    def bookmarks_by_article(cls, user_id: int, article_ids):
        """{article_id: [bookmark json]} in one query.

        Batch form of get_all_user_bookmarks_for_article_title: the feed would
        otherwise ask once per article.
        """
        from zeeguu.core.model.user_word import UserWord

        if not article_ids:
            return {}
        rows = (
            db.session.query(ArticleTitleContext.article_id, Bookmark)
            .select_from(Bookmark)
            .join(ArticleTitleContext)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(ArticleTitleContext.article_id.in_(article_ids))
            .filter(UserWord.user_id == user_id)
        ).all()
        result = {}
        for key, bookmark in rows:
            result.setdefault(key, []).append(bookmark.to_json(True))
        return result
