from zeeguu.core.model import db
import sqlalchemy


class ArticleFragmentContext(db.Model):
    """
    A context that is found in a fragment of an Article.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    from zeeguu.core.model.bookmark import Bookmark

    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)
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
        try:
            return cls.query.filter(
                cls.bookmark == bookmark,
                cls.article_fragment == article_fragment,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(
                bookmark,
                article_fragment,
            )
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_article_fragment(
        cls, user_id: int, article_fragment_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model.bookmark import Bookmark, UserMeaning

        result = (
            Bookmark.query.join(cls)
            .join(UserMeaning)
            .filter(cls.article_fragment_id == article_fragment_id)
            .filter(UserMeaning.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]
