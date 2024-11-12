from zeeguu.core.model import db
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from enum import IntEnum


class TopicOriginType(IntEnum):
    URL_PARSED = 1
    HARDSET = 2
    INFERRED = 3


class ArticleTopicMap(db.Model):
    __tablename__ = "article_topic_map"
    # Constants used for origin_type
    article_id = Column(ForeignKey("article.id"), primary_key=True)
    topic_id = Column(ForeignKey("topic.id"), primary_key=True)
    origin_type = Column(Integer)
    article = relationship("Article", back_populates="topics")
    topic = relationship("Topic", back_populates="articles")
