import zeeguu.core
from sqlalchemy import Column, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound


from zeeguu.core.model import db


class DifficultyLingoRank(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    from zeeguu.core.model.article import Article

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    difficulty = Column(Float)

    def __init__(self, article, difficulty) -> None:
        super().__init__()
        self.article = article
        self.difficulty = difficulty

    @classmethod
    def value_for_article(cls, article):
        try:
            return cls.query.filter_by(article_id=article.id).one().difficulty
        except NoResultFound:
            return None
