from .db import db
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm.exc import NoResultFound
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

    def __init__(self, article, topic, origin_type):
        self.article = article
        self.topic = topic
        self.origin_type = origin_type

    @classmethod
    def create_or_update(cls, article, topic, origin_type: TopicOriginType):
        try:
            topic_mapping = (
                cls.query.filter(cls.article == article)
                .filter(cls.topic == topic)
                .one()
            )
            if topic_mapping.origin_type != origin_type:
                print(
                    f"## Article Topic Mapping Found '{topic.title}', overriding {topic_mapping.origin_type} with {origin_type}"
                )
            topic_mapping.origin_type = origin_type
        except NoResultFound:
            topic_mapping = ArticleTopicMap(
                article=article, topic=topic, origin_type=origin_type
            )

        return topic_mapping

    @classmethod
    def create_if_doesnt_exists(cls, article, topic, origin_type: TopicOriginType):
        try:
            topic_mapping = (
                cls.query.filter(cls.article == article)
                .filter(cls.topic == topic)
                .one()
            )
            return None
        except NoResultFound:
            topic_mapping = ArticleTopicMap(
                article=article, topic=topic, origin_type=origin_type
            )
        return topic_mapping
