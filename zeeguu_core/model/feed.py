# -*- coding: utf8 -*-

import time
from datetime import datetime

import feedparser
import requests
import sqlalchemy.orm.exc
from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from zeeguu_core.constants import JSON_TIME_FORMAT, SIMPLE_TIME_FORMAT
from zeeguu_core.model.language import Language
from zeeguu_core.model.url import Url

db = zeeguu_core.db


class RSSFeed(db.Model):
    __table_args__ = {'mysql_collate': 'utf8_bin'}
    __tablename__ = 'rss_feed'

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

    def __init__(self, url, title, description, image_url=None, icon_name=None, language=None):
        self.url = url
        self.image_url = image_url
        self.icon_name = icon_name
        self.title = title
        self.language = language
        self.description = description
        self.last_crawled_time = datetime(2001, 1, 2)

    def __str__(self):
        language = "unknown"
        if self.language:
            language = self.language.code

        return f'{self.title, language}'

    def __repr__(self):
        return str(self)

    @classmethod
    def from_url(cls, url: str):
        data = feedparser.parse(url)

        try:
            title = data.feed.title
        except:
            title = ""

        try:
            description = data.feed.subtitle
        except:
            description = None

        try:
            image_url_string = data.feed.image.href
            print(f'Found image url at: {image_url_string}')
        except:
            print('Could not find any image url.')

        feed_url = Url(url, title)

        return RSSFeed(feed_url, title, description)


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
            image_url='',
            icon_name=self.icon_name
        )

    def feed_items(self, last_retrieval_time_from_DB = None):
        """

        :return: a dictionary with info about that feed
        extracted by feedparser
        and including: title, url, content, summary, time
        """

        if not last_retrieval_time_from_DB:
            last_retrieval_time_from_DB = datetime(1980,1,1)

        def publishing_date(item):
            # this used to be updated_parsed but cf the deprecation
            # warning we changed to published_parsed instead.
            try:
                return item.published_parsed
            except:
                # March 8 -- added back in updated_parsed;
                # curious if this fixes the problem in some
                # cases; to find out, we log

                zeeguu_core.log(f'trying updated_parsed where published_parsed failed for {item.get("link", "")} in the context of {self.url.as_string()}')
                result = item.updated_parsed
                return result

        response = requests.get(self.url.as_string())
        feed_data = feedparser.parse(response.text)

        skipped_due_to_time = 0
        feed_items = []
        skipped_items = []
        zeeguu_core.log(f"** Articles in feed: {len(feed_data.entries)}")
        for item in feed_data.entries:
            try:
                published_string = time.strftime(SIMPLE_TIME_FORMAT, publishing_date(item))

                this_entry_time = datetime.strptime(published_string, SIMPLE_TIME_FORMAT)
                this_entry_time = this_entry_time.replace(tzinfo=None)

                new_item_data_dict = dict(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    content=item.get("content", ""),
                    summary=item.get("summary", ""),
                    published=published_string,
                    published_datetime=this_entry_time
                )

                if this_entry_time > last_retrieval_time_from_DB:
                    feed_items.append(new_item_data_dict)
                else:
                    skipped_due_to_time+=1
                    skipped_items.append(new_item_data_dict)

            except AttributeError as e:
                zeeguu_core.log(f'Exception {e} while trying to retrieve {item.get("link", "")}')


        sorted_skipped_items = sorted(skipped_items, key= lambda x:x['published_datetime'])
        for each in sorted_skipped_items:
            zeeguu_core.debug(f"- skipped: {each['published_datetime']} - {each['title']}")

        for each in feed_items:
            zeeguu_core.debug(f"- to download: {each['published_datetime']} - {each['title']}")

        zeeguu_core.log(f'*** Skipped due to time: {len(skipped_items)} ')
        zeeguu_core.log(f"*** To download: {len(feed_items)}")

        return feed_items

    @classmethod
    def exists(cls, rss_feed):
        try:
            cls.query.filter(
                cls.url == rss_feed.url
            ).one()
            return True
        except NoResultFound:
            return False

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
    def find_by_url(cls, url):
        try:
            result = cls.query.filter(cls.url == url).one()
            return result
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(cls, session, url, title, description, icon_name, language: Language):
        try:
            result = (cls.query.filter(cls.url == url)
                      .filter(cls.title == title)
                      .filter(cls.language == language)
                      .filter(cls.description == description)
                      .one())
            return result
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(url, title, description, icon_name=icon_name, language=language)
            session.add(new)
            session.commit()
            return new

    # although it seems to not be used by anybody,
    # this method is being used from the zeeguu-api
    @classmethod
    def find_for_language_id(cls, language_code):
        language = Language.find(language_code)
        return cls.query.filter(cls.language == language).all()

    def get_articles(self, limit=None, after_date=None, most_recent_first=False, easiest_first=False):
        """

            Articles for this feed from the article DB

        :param limit:
        :param after_date:
        :param most_recent_first:
        :param easiest_first:
        :return:
        """

        from zeeguu_core.model import Article

        if not after_date:
            after_date = datetime(2001, 1, 1)

        try:
            q = (Article.query.
                 filter(Article.rss_feed == self).
                 filter(Article.broken == 0).
                 filter(Article.published_time >= after_date).
                 filter(Article.word_count > Article.MINIMUM_WORD_COUNT))

            if most_recent_first:
                q = q.order_by(Article.published_time.desc())
            if easiest_first:
                q = q.order_by(Article.fk_difficulty)

            return q.limit(limit).all()

        except Exception as e:
            raise (e)
            return None
