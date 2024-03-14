from zeeguu.core.model import db
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship


class ArticleTopicKeywordMap(db.Model):
    __tablename__ = "article_topic_keyword_map"
    article_id = Column(ForeignKey("article.id"), primary_key=True)
    topic_keyword_id = Column(ForeignKey("topic_keyword.id"), primary_key=True)
    rank = Column(Integer)
    article = relationship("Article", back_populates="topic_keywords")
    topic_keyword = relationship("TopicKeyword", back_populates="articles")
