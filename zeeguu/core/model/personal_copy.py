from zeeguu.core.model.article import Article
from zeeguu.core.model.user import User
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

import zeeguu

db = zeeguu.core.db


class PersonalCopy(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    def __init__(self, user, article):

        self.user = user
        self.article = article

    @classmethod
    def exists_for(user_id, article_id):
        return len(
            PersonalCopy.query.filter(user_id=user_id, article_id=article_id).all()
        )
