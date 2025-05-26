from zeeguu.logging import logp

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.article_topic_map import ArticleTopicMap
from datetime import datetime


class Topic(db.Model):
    """
    The Topics are standerdized accross all languages.

    Each UrlKeyword can be associated with one Topic
    which are used to infer topics in articles which haven't got any topic.

    This relationship is stored in ArticleTopicMap.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "topic"

    id = Column(Integer, primary_key=True)

    title = Column(String(64))
    articles = relationship("ArticleTopicMap", back_populates="topic")
    language_topic_available_cache = {}

    def __init__(self, title):
        self.title = title

    def __repr__(self):
        return f"<Topic {self.title}>"

    def as_dictionary(self):

        return dict(
            id=self.id,
            title=self.title,
        )

    def all_articles(self, limit=2000):

        from zeeguu.core.model import Article

        if hasattr(Topic, "cached_articles") and (
            self.cached_articles.get(self.id, None)
        ):
            logp(f"Topic: getting the cached articles for topic: {self.title}")
            all_ids = Topic.cached_articles[self.id]
            return Article.query.filter(Article.id.in_(all_ids)).all()

        if not hasattr(Topic, "cached_articles"):
            Topic.cached_articles = {}

        logp("computing and caching the articles for topic: " + self.title)
        Topic.cached_articles[self.id] = [
            each.id
            for each in Article.query.order_by(Article.published_time.desc())
            .filter(Article.topics.any(id=self.id))
            .limit(limit)
        ]

        all_ids = Topic.cached_articles[self.id]
        return Article.query.filter(Article.id.in_(all_ids)).all()

    def clear_all_articles_cache(self):
        Topic.cached_articles[self.id] = None

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
    def get_all_topics(cls, language: Language = None):
        from zeeguu.core.model.article import Article

        def update_available_topic_cache():
            topics_for_language = (
                Topic.query.join(ArticleTopicMap)
                .join(Article)
                .filter(Article.language_id == language.id)
                .distinct(Topic.id)
                .all()
            )
            cls.language_topic_available_cache[language.id] = (
                topics_for_language,
                datetime.now(),
            )

        if language is None:
            return Topic.query.order_by(Topic.title).all()
        topics_available, last_check = cls.language_topic_available_cache.get(
            language.id, (None, None)
        )

        if last_check is None:
            update_available_topic_cache()
        else:
            time_since_last_check = datetime.now() - last_check
            if time_since_last_check.days > 7:
                update_available_topic_cache()

        topics_available = cls.language_topic_available_cache[language.id][0]
        return topics_available
