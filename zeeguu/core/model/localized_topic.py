from sqlalchemy.orm import relationship

import zeeguu.core

from sqlalchemy import Column, Integer, String, ForeignKey, and_

from zeeguu.core.model import db


class LocalizedTopic(db.Model):
    """

    A localized topic is a localized version of a topic,
    it is the same topic but translated and with
    the added language_id and localized keywords.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    from zeeguu.core.model.topic import Topic

    topic_id = Column(Integer, ForeignKey(Topic.id))
    topic = relationship(Topic)

    from zeeguu.core.model.language import Language

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    topic_translated = Column(String(30))

    keywords = Column(String(1024))

    def __init__(
        self,
        topic: Topic,
        language: Language,
        topic_translated: str,
        keywords: str = "",
    ):
        self.topic = topic
        self.language = language
        self.topic_translated = topic_translated
        self.keywords = keywords

    def __repr__(self):
        return f"<Localized topic {self.topic} ({self.language}) : {self.topic_translated}>"

    def matches_article(self, article):
        keywords = self.keywords.strip().split(" ")

        for keyword in keywords:
            if keyword != "" and (
                keyword in article.url.as_string() or keyword in article.title
            ):
                return True

        return False

    def all_articles(self):
        from zeeguu.core.model import Article

        return Article.query.filter(Article.topics.any(id=self.topic_id)).all()

    @classmethod
    def all_for_language(cls, language):
        return (cls.query.filter(cls.language == language)).all()
