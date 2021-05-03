import sqlalchemy
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UnicodeText, Table

from zeeguu_core.constants import JSON_TIME_FORMAT
from zeeguu_core.language.difficulty_estimator_factory import DifficultyEstimatorFactory
from langdetect import detect


db = zeeguu_core.db

article_topic_map = Table(
    "article_topic_map",
    db.Model.metadata,
    Column("article_id", Integer, ForeignKey("article.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)

MAX_CHAR_COUNT_IN_SUMMARY = 300


class Article(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    title = Column(String(512))
    authors = Column(UnicodeText)
    content = Column(UnicodeText())
    summary = Column(UnicodeText)
    word_count = Column(Integer)
    published_time = Column(DateTime)
    fk_difficulty = Column(Integer)
    broken = Column(Integer)

    from zeeguu_core.model.url import Url

    from zeeguu_core.model.feed import RSSFeed

    from zeeguu_core.model.language import Language

    rss_feed_id = Column(Integer, ForeignKey(RSSFeed.id))
    rss_feed = relationship(RSSFeed)

    url_id = Column(Integer, ForeignKey(Url.id), unique=True)
    url = relationship(Url)

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    from zeeguu_core.model.user import User

    uploader_id = Column(Integer, ForeignKey(User.id))
    uploader = relationship(User)

    from zeeguu_core.model.topic import Topic

    topics = relationship(
        Topic, secondary="article_topic_map", backref=backref("articles")
    )

    # Few words in an article is very often not an
    # actual article but the caption for a video / comic.
    # Or maybe an article that's behind a paywall and
    # has only the first paragraph available
    MINIMUM_WORD_COUNT = 90

    def __init__(
        self,
        url,
        title,
        authors,
        content,
        summary,
        published_time,
        rss_feed,
        language,
        uploader=None,
        broken=0,
    ):
        self.url = url
        self.title = title
        self.authors = authors
        self.content = content
        self.summary = summary
        self.published_time = published_time
        self.rss_feed = rss_feed
        self.language = language
        self.uploader = uploader
        self.broken = broken

        fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
        fk_difficulty = fk_estimator.estimate_difficulty(
            self.content, self.language, None
        )["grade"]

        # easier to store integer in the DB
        # otherwise we have to use Decimal, and it's not supported on all dbs
        self.fk_difficulty = fk_difficulty
        self.word_count = len(self.content.split())

    def __repr__(self):
        return f"<Article {self.title} (w: {self.word_count}, d: {self.fk_difficulty}) ({self.url})>"

    def vote_broken(self):
        # somebody could vote that this article is broken
        self.broken += 1

    def topics_as_string(self):
        topics = ""
        for topic in self.topics:
            topics += topic.title + " "
        return topics

    def contains_any_of(self, keywords: list):
        for each in keywords:
            if self.title.find(each) >= 0:
                return True
        return False

    def article_info(self, with_content=False):
        """

            This is the data that is sent over the API
            to the Reader. Whatever the reader needs
            must be here.

        :return:
        """

        summary = self.content[:MAX_CHAR_COUNT_IN_SUMMARY]

        result_dict = dict(
            id=self.id,
            title=self.title,
            summary=summary,
            language=self.language.code,
            topics=self.topics_as_string(),
            metrics=dict(
                difficulty=self.fk_difficulty / 100, word_count=self.word_count
            ),
        )

        if self.authors:
            result_dict["authors"] = self.authors
        elif self.uploader:
            result_dict["authors"] = self.uploader.name
        else:
            result_dict["authors"] = ""

        if self.url:
            result_dict["url"] = self.url.as_string()

        if self.published_time:
            result_dict["published"] = self.published_time.strftime(JSON_TIME_FORMAT)

        if self.rss_feed:
            result_dict["feed_id"] = (self.rss_feed.id,)
            result_dict["icon_name"] = self.rss_feed.icon_name

            # TO DO: remove feed_image_url from RSSFeed --- this is here for compatibility
            # until the codebase is moved to zorg.
            if self.rss_feed.image_url:
                result_dict["feed_image_url"] = self.rss_feed.image_url.as_string()

        if with_content:
            result_dict["content"] = self.content

        return result_dict

    def article_info_for_teacher(self):
        from zeeguu_core.model import CohortArticleMap

        info = self.article_info()
        info["cohorts"] = CohortArticleMap.get_cohorts_for_article(self)

        return info

    def is_owned_by(self, user):
        return self.uploader_id == user.id

    def add_topic(self, topic):
        self.topics.append(topic)

    def add_search(self, search):
        self.searches.append(search)

    def remove_search(self, search):
        print("trying to remove a search term")
        self.searches.remove(search)

    def star_for_user(self, session, user, state=True):
        from zeeguu_core.model.user_article import UserArticle

        ua = UserArticle.find_or_create(session, user, self)
        ua.set_starred(state)
        session.add(ua)

    @classmethod
    def own_texts_for_user(cls, user):
        return cls.query.filter(cls.uploader_id == user.id).all()

    @classmethod
    def create_from_upload(cls, session, title, content, uploader, language):

        new_article = Article(
            None, title, None, content, None, None, None, language, uploader
        )
        session.add(new_article)

        session.commit()
        return new_article.id

    @classmethod
    def find_or_create(cls, session, _url: str, language=None, sleep_a_bit=False):
        """

            If not found, download and extract all
            the required info for this article.

        :param url:
        :return:
        """
        from zeeguu_core.model import Url, Article, Language
        import newspaper

        url = Url.extract_canonical_url(_url)

        try:
            found = cls.find(url)
            if found:
                return found

            art = newspaper.Article(url=url)
            art.download()
            art.parse()

            if art.text == "":
                # raise Exception("Newspaper got empty article from: " + url)
                art.text = "N/A"
                # this is a temporary solution for allowing translations
                # on pages that do not have "articles" downloadable by newspaper.

            if sleep_a_bit:
                import time
                from random import randint

                print("GOT: " + url)
                sleep_time = randint(3, 33)
                print(
                    f"sleeping for {sleep_time}s... so we don't annoy our friendly servers"
                )
                time.sleep(sleep_time)

            if not language:
                if art.meta_lang == "":
                    art.meta_lang = detect(art.text)
                    zeeguu_core.log(f"langdetect: {art.meta_lang} for {url}")
                language = Language.find_or_create(art.meta_lang)

            # Create new article and save it to DB
            url_object = Url.find_or_create(session, url)

            new_article = Article(
                url_object,
                art.title,
                ", ".join(art.authors),
                art.text[0:32000],  # any article longer than this will be truncated...
                art.summary,
                None,
                None,
                language,
            )
            session.add(new_article)

            session.commit()

            return new_article
        except sqlalchemy.exc.IntegrityError or sqlalchemy.exc.DatabaseError:
            for i in range(10):
                try:
                    session.rollback()
                    u = cls.find(url)
                    print("Found article by url after recovering from race")
                    return u
                except:
                    print("Exception of second degree in article..." + str(i))
                    time.sleep(0.3)
                    continue
                break

    @classmethod
    def find_by_id(cls, id: int):
        return Article.query.filter(Article.id == id).first()

    @classmethod
    def find(cls, url: str):
        """

            Find by url

        :return: object or None if not found
        """

        from zeeguu_core.model import Url

        try:
            url_object = Url.find(url)
            return (cls.query.filter(cls.url == url_object)).one()
        except NoResultFound:
            return None

    @classmethod
    def all_older_than(cls, days):
        import datetime

        today = datetime.date.today()
        long_ago = today - datetime.timedelta(days)
        try:
            return cls.query.filter(cls.published_time < long_ago).all()

        except NoResultFound:
            return []

    @classmethod
    def exists(cls, article):
        try:
            cls.query.filter(cls.url == article.url).one()
            return True
        except NoResultFound:
            return False

    @classmethod
    def with_title_containing(cls, needle):
        return cls.query.filter(cls.title.like(f"%{needle}%")).all()
