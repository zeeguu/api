from zeeguu.core.model import db
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from enum import IntEnum


class TopicOriginType(IntEnum):
    URL_PARSED = 1
    HARDSET = 2
    INFERRED = 3


class ArticleTopicMap(db.Model):
    __tablename__ = "new_article_topic_map"
    # Constants used for origin_type
    article_id = Column(ForeignKey("article.id"), primary_key=True)
    new_topic_id = Column(ForeignKey("new_topic.id"), primary_key=True)
    origin_type = Column(Integer)
    article = relationship("Article", back_populates="new_topics")
    new_topic = relationship("Topic", back_populates="articles")
