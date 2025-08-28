from zeeguu.core.model.article import Article
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
import sqlalchemy


class ArticleSummaryContext(db.Model):
    """
    A context that is found in a summary of an Article.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)
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
        return f"<ArticleSummaryContext b:{self.bookmark_id}, a:{self.article_id}>"

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
        try:
            return cls.query.filter(
                cls.bookmark == bookmark,
                cls.article == article,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(
                bookmark,
                article,
            )
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_article_summary(
        cls, user_id: int, article_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model.user_word import UserWord

        result = (
            Bookmark.query.join(ArticleSummaryContext)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(ArticleSummaryContext.article_id == article_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]