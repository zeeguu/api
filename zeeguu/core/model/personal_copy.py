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
    def exists_for(cls, user, article):
        return len(
            PersonalCopy.query.filter_by(user_id=user.id, article_id=article.id).all()
        )

    @classmethod
    def all_for(cls, user):
        return (
            Article.query.join(PersonalCopy)
            .filter(PersonalCopy.user_id == user.id)
            .all()
        )

    @classmethod
    def make_for(cls, user, article, session):
        new_personal_copy = PersonalCopy(user, article)
        session.add(new_personal_copy)
        session.commit()
