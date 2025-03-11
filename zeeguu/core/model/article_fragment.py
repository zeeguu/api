from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import db


class ArticleFragment(db.Model):
    """
    The article fragment represents roughly an HTML tag in the article.
    We use this to keep some of the rich formatting from the webpage, such as H1, Imgs etc.
    """

    from zeeguu.core.model.new_text import NewText
    from zeeguu.core.model.article import Article

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    text_id = Column(Integer, ForeignKey(NewText.id))
    text = relationship(NewText, foreign_keys="ArticleFragment.text_id")

    order = Column(Integer)
    formatting = Column(String(20))

    def __init__(self, article: Article, text: str, order: int, formatting: str):
        self.article = article
        self.text = text
        self.formatting = formatting
        self.order = order

    @classmethod
    def find_by_id(cls, id: int):
        """
        Retrieve a specific ArticleFragment by its ID.
        Args:
            id (int): The primary key of the ArticleFragment to retrieve.
        Returns:
            ArticleFragment instance or None if not found.
        """
        try:
            return cls.query.filter_by(id=id).one()
        except NoResultFound:
            return None

    @classmethod
    def find_by_article_order(cls, article_id: int, order: int):
        try:
            return (
                cls.query.filter(cls.article_id == article_id)
                .filter(cls.order == order)
                .one()
            )
        except NoResultFound:
            return None

    @classmethod
    def get_all_article_fragments_in_order(cls, article_id: int):
        try:
            return (
                cls.query.filter_by(article_id=article_id)
                .order_by(cls.order.asc())
                .all()
            )
        except NoResultFound:
            return []

    @classmethod
    def find_or_create(
        cls,
        session,
        article,
        text: str,
        order: int,
        formatting: str = None,
        commit=True,
    ):
        from zeeguu.core.model.new_text import NewText

        text_row = NewText.find_or_create(session, text, commit=commit)
        try:
            return cls.query.filter_by(
                article=article, text_id=text_row.id, order=order, formatting=formatting
            ).one()

        except NoResultFound:
            new = cls(article, text_row, order, formatting)
            session.add(new)
            if commit:
                session.commit()
            return new
