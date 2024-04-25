from zeeguu.logging import logp

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from zeeguu.core.model import db


class NewTopic(db.Model):
    """
    The New Topics are standerdized accross all languages.

    Each TopicKeyword can be associated with one New Topic
    which are used to infer topics in articles which haven't got any topic.

    This relationship is stored in NewArticleTopicMap.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "new_topic"

    id = Column(Integer, primary_key=True)

    title = Column(String(64))
    articles = relationship("NewArticleTopicMap", back_populates="new_topic")

    def __init__(self, title):
        self.title = title

    def __repr__(self):
        return f"<NewTopic {self.title}>"

    def as_dictionary(self):

        return dict(
            id=self.id,
            title=self.title,
        )

    def all_articles(self, limit=2000):

        from zeeguu.core.model import Article

        if hasattr(NewTopic, "cached_articles") and (
            self.cached_articles.get(self.id, None)
        ):
            logp(f"Topic: getting the cached articles for topic: {self.title}")
            all_ids = NewTopic.cached_articles[self.id]
            return Article.query.filter(Article.id.in_(all_ids)).all()

        if not hasattr(NewTopic, "cached_articles"):
            NewTopic.cached_articles = {}

        logp("computing and caching the articles for topic: " + self.title)
        NewTopic.cached_articles[self.id] = [
            each.id
            for each in Article.query.order_by(Article.published_time.desc())
            .filter(Article.topics.any(id=self.id))
            .limit(limit)
        ]

        all_ids = NewTopic.cached_articles[self.id]
        return Article.query.filter(Article.id.in_(all_ids)).all()

    def clear_all_articles_cache(self):
        NewTopic.cached_articles[self.id] = None

    @classmethod
    def find(cls, name: str):
        try:
            return cls.query.filter(cls.title == name).one()
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None

    @classmethod
    def find_by_id(cls, i):
        try:
            result = cls.query.filter(cls.id == i).one()
            return result
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None

    @classmethod
    def get_all_topics(cls):
        return NewTopic.query.order_by(NewTopic.title).all()
