# -*- coding: utf8 -*-

from datetime import datetime

import sqlalchemy.orm.exc
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.logging import log, debug
from zeeguu.core.model.language import Language
from zeeguu.core.model.url import Url
from zeeguu.core.feed_handler import FEED_TYPE_TO_FEED_HANDLER

import zeeguu

from zeeguu.core.model import db


class Feed(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "feed"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(2083))
    description = db.Column(db.String(2083))

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)

    url_id = db.Column(db.Integer, db.ForeignKey(Url.id))
    url = db.relationship(Url, foreign_keys=url_id)

    image_url_id = db.Column(db.Integer, db.ForeignKey(Url.id))
    image_url = db.relationship(Url, foreign_keys=image_url_id)

    icon_name = db.Column(db.String(2083))

    last_crawled_time = db.Column(db.DateTime)

    deactivated = db.Column(db.Integer)

    feed_type = db.Column(db.Integer)

    feed_handler = None

    def __init__(
            self,
            url,
            title,
            description,
            image_url=None,
            icon_name=None,
            language=None,
            feed_type=0,
            feed_handler=None,
    ):
        self.url = url
        self.image_url = image_url
        self.icon_name = icon_name
        self.title = title
        self.language = language
        self.description = description
        self.last_crawled_time = datetime(2001, 1, 2)
        self.deactivated = 0
        self.feed_type = feed_type
        self.feed_handler = feed_handler

    def __str__(self):
        language = "unknown"
        if self.language:
            language = self.language.code

        return f"{self.title, language}"

    def __repr__(self):
        return str(self)

    @classmethod
    def from_url(cls, url: str, feed_type: int):
        try:
            feed_handler = FEED_TYPE_TO_FEED_HANDLER[feed_type](url, feed_type)
            feed_url = Url(feed_handler.url, feed_handler.title)
        except KeyError as e:
            log(f"Feed Handler not defined for type '{feed_type}'.")

        return Feed(
            feed_url,
            feed_handler.title,
            feed_handler.description,
            feed_type=feed_type,
            feed_handler=feed_handler,
        )

    def initializeFeedHandler(self):
        if self.feed_handler is None:
            self.feed_handler = FEED_TYPE_TO_FEED_HANDLER[self.feed_type](str(self.url), self.feed_type)

    def as_dictionary(self):
        language = "unknown_lang"
        if self.language:
            language = self.language.code

        return dict(
            id=self.id,
            title=self.title,
            url=self.url.as_string(),
            description=self.description,
            language=language,
            image_url="",
            icon_name=self.icon_name,
            feed_type=self.feed_type,
        )

    def feed_items(self, last_retrieval_time_from_DB=None):
        """
        :return: a dictionary with info about that feed
        extracted by feedparser
        and including: title, url, content, summary, time
        """
        # Since loading this from the DB will cause the file
        # handler to be set to none, we initialize it here.
        self.initializeFeedHandler()

        if not last_retrieval_time_from_DB:
            last_retrieval_time_from_DB = datetime(1980, 1, 1)

        feed_candidates = self.feed_handler.get_feed_articles()

        skipped_due_to_time = 0
        feed_items = []
        skipped_items = []
        for item in feed_candidates:
            this_entry_time = item["published_datetime"]
            this_entry_time = this_entry_time.replace(tzinfo=None)
            if this_entry_time > last_retrieval_time_from_DB:
                feed_items.append(item)
            else:
                skipped_due_to_time += 1
                skipped_items.append(item)

            sorted_skipped_items = sorted(
                skipped_items, key=lambda x: x["published_datetime"]
            )
            for each in sorted_skipped_items:
                debug(f"- skipped: {each['published_datetime']} - {each['title']}")

            for each in feed_items:
                debug(f"- to download: {each['published_datetime']} - {each['title']}")

            log(f"*** Skipped due to time: {len(skipped_items)} ")
            log(f"*** To download: {len(feed_items)}")

        return feed_items

    @classmethod
    def exists(cls, feed):
        try:
            cls.query.filter(cls.url == feed.url).one()
            return True
        except NoResultFound:
            return False

    def feed_health_info(self):
        feed_items = self.feed_items()
        if not feed_items:
            return "Feed seems broken. No items found."
        else:
            count = len(feed_items)
            return f"Feed seems healthy: {count} items found. "

    @classmethod
    def find_by_id(cls, i):
        try:
            result = cls.query.filter(cls.id == i).one()
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None

    @classmethod
    def find_by_url(cls, url):
        try:
            result = cls.query.filter(cls.url == url).one()
            return result
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
            cls,
            session,
            url,
            title,
            description,
            icon_name,
            language: Language,
            feed_type,
    ):
        try:
            result = (
                cls.query.filter(cls.url == url)
                .filter(cls.title == title)
                .filter(cls.language == language)
                .filter(cls.description == description)
                .filter(cls.feed_type == feed_type)
                .one()
            )
            return result
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(
                url,
                title,
                description,
                icon_name=icon_name,
                language=language,
                feed_type=feed_type,
            )
            session.add(new)
            session.commit()
            return new

    # although it seems to not be used by anybody,
    # this method is being used from the zeeguu-endpoints
    @classmethod
    def find_for_language_id(cls, language_code):
        language = Language.find(language_code)
        return cls.query.filter(cls.language == language).all()

    def get_articles(
            self, limit=None, after_date=None, most_recent_first=False, easiest_first=False
    ):
        """

            Articles for this feed from the article DB

        :param limit:
        :param after_date:
        :param most_recent_first:
        :param easiest_first:
        :return:
        """

        from zeeguu.core.model import Article

        if not after_date:
            after_date = datetime(2001, 1, 1)

        try:
            q = (
                Article.query.filter(Article.feed == self)
                .filter(Article.broken == 0)
                .filter(Article.published_time >= after_date)
                .filter(Article.word_count > Article.MINIMUM_WORD_COUNT)
            )

            if most_recent_first:
                q = q.order_by(Article.published_time.desc())
            if easiest_first:
                q = q.order_by(Article.fk_difficulty)

            return q.limit(limit).all()

        except Exception as e:
            raise (e)
            return None
