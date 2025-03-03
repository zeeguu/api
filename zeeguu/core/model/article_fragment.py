from sqlalchemy import Column, String, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model.article import Article
from zeeguu.core.model import db


class ArticleFragment(db.Model):
    """
    The article fragment represents roughly an HTML tag in the article.
    We use this to keep some of the rich formatting from the webpage, such as H1, Imgs etc.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)
    order = Column(Integer)

    text = Column(UnicodeText)
    formatting = Column(String(20))

    def __init__(self, article: Article, order: int, text: str, formatting: str):
        self.article = article
        self.text = text
        self.formatting = formatting
        self.order = order

    @classmethod
    def find(cls, id: int):
        """
        Retrieve a specific ArticleFragment by its ID.
        Args:
            id (int): The primary key of the ArticleFragment to retrieve.
        Returns:
            ArticleFragment instance or None if not found.
        """
        try:
            return cls.query.filter_by(id=id).order_by(cls.date.desc()).first()
        except NoResultFound:
            return None

    @classmethod
    def get_all_article_fragments_in_order(cls, article_id: int):
        return (
            cls.query.filter_by(article_id=article_id).order_by(cls.order.asc()).all()
        )

    @classmethod
    def find_or_create(
        cls, session, article_id: int, text: str, order: int, formatting: str
    ):
        try:
            return cls.query.filter_by(
                article_id=article_id, text=text, order=order, formatting=formatting
            ).one()

        except NoResultFound:
            article = Article.find_by_id(article_id)
            new = cls(article, text, order, formatting)
            session.add(new)
            session.commit()
            return new
