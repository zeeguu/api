from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model import db, Context
import sqlalchemy


class ArticleFragmentContext(db.Model):
    """
    A context that is found in a fragment of an Article.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    context_id = db.Column(db.Integer, db.ForeignKey(Context.id), nullable=False)
    context = db.relationship(Context)

    article_fragment_id = db.Column(db.Integer, db.ForeignKey(ArticleFragment.id))
    article_fragment = db.relationship(ArticleFragment)

    # Defines the start of context (sentence_i and token_i) in the fragment.
    sentence_i = db.Column(db.Integer)
    token_i = db.Column(db.Integer)

    def __init__(
        self,
        context,
        article,
        sentence_i,
        token_i,
    ):
        self.context = context
        self.article = article
        self.sentence_i = sentence_i
        self.token_i = token_i

    def __repr__(self):
        return f"<ArticleFragmentContext a:{self.article_fragment_id}, c:{self.context_id}>"

    @classmethod
    def find_or_create(
        cls,
        session,
        content,
        article,
        sentence_i,
        token_i,
    ):
        try:
            return cls.query.filter(
                cls.context_id == content.id,
                cls.article_fragment_id == article.id,
                cls.sentence_i == sentence_i,
                cls.token_i == token_i,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(
                content,
                article,
                sentence_i,
                token_i,
            )
            session.add(new)
            session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_article_fragment(
        cls, user_id: int, article_fragment_id: int
    ):
        from zeeguu.core.model.bookmark import Bookmark

        result = (
            Bookmark.query.filter(Bookmark.user_id == user_id)
            .filter(Bookmark.context_id == cls.context_id)
            .filter(cls.article_fragment_id == article_fragment_id)
        ).all()

        return [each for each in result]
