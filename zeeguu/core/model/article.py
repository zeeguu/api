import re

from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UnicodeText, desc
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model.article_topic_map import TopicOriginType

from zeeguu.core.model.article_url_keyword_map import ArticleUrlKeywordMap
from zeeguu.core.model.article_topic_map import ArticleTopicMap
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.core.language.fk_to_cefr import fk_to_cefr

from zeeguu.core.model import db

MAX_CHAR_COUNT_IN_SUMMARY = 300
MARKED_BROKEN_DUE_TO_LOW_QUALITY = 100

HTML_TAG_CLEANR = re.compile("<[^>]*>")

MULTIPLE_NEWLINES = re.compile(r"\n\s*\n")
# \n matches a line-feed (newline) character (ASCII 10)
# \s matches any whitespace character (equivalent to [\r\n\t\f\v  ])
# \n matches a line-feed (newline) character (ASCII 10)


"""
    Wed 23, Feb
    - added htmlContent - which should, from now on, be the favorite 
    content to be used when possible ; by default this is going to be 
    null; 

    April 15
    - added uploader_id - is set in the case in which a user uploads 
    their own text... 

"""


class Article(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    title = Column(String(512))
    authors = Column(String(128))
    content = Column(UnicodeText())

    htmlContent = Column(UnicodeText())
    summary = Column(UnicodeText)
    word_count = Column(Integer)
    published_time = Column(DateTime)
    fk_difficulty = Column(Integer)
    broken = Column(Integer)
    deleted = Column(Integer)
    video = Column(Integer)

    from zeeguu.core.model.url import Url

    from zeeguu.core.model.feed import Feed

    from zeeguu.core.model.language import Language

    from zeeguu.core.model.source import Source

    source_id = Column(Integer, ForeignKey(Source.id), unique=True)
    source = relationship(Source, foreign_keys="Article.source_id")

    feed_id = Column(Integer, ForeignKey(Feed.id))
    feed = relationship(Feed)

    url_id = Column(Integer, ForeignKey(Url.id), unique=True)
    img_url_id = Column(Integer, ForeignKey(Url.id), unique=True)
    url = relationship(Url, foreign_keys="Article.url_id")
    img_url = relationship(Url, foreign_keys="Article.img_url_id")

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    from zeeguu.core.model.user import User

    uploader_id = Column(Integer, ForeignKey(User.id))
    uploader = relationship(User)

    topics = relationship(
        "ArticleTopicMap",
        back_populates="article",
        # passive_deletes = tells SQLAlchemy to rely on the database's CASCADE behavior
        # instead of trying to manage the deletion itself
        passive_deletes=True,
    )

    url_keywords = relationship(
        "ArticleUrlKeywordMap",
        back_populates="article",
        # passive_deletes = tells SQLAlchemy to rely on the database's
        # CASCADE behavior instead of trying to manage the deletion itself
        passive_deletes=True,
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
        source,
        summary,
        published_time,
        feed,
        language,
        htmlContent="",
        uploader=None,
        found_by_user=0,  # tracks whether the user found this article (as opposed to us recommending it)
        broken=0,
        deleted=0,
        video=0,
        img_url=None,
    ):
        if not summary:
            summary = source.get_content()[:MAX_CHAR_COUNT_IN_SUMMARY]

        self.url = url
        self.title = title
        self.authors = authors
        self.source = source
        # Remove once we have source migration complete.
        self.content = source.get_content()
        self.htmlContent = htmlContent
        self.summary = summary
        self.published_time = published_time
        self.feed = feed
        self.language = language
        self.uploader = uploader
        self.userFound = found_by_user
        self.broken = broken
        self.deleted = deleted
        self.video = video
        self.img_url = img_url
        self.fk_cefr_level = None
        # Delete once it's migrated.
        self.word_count = source.word_count
        self.fk_difficulty = source.fk_difficulty

    def __repr__(self):
        return f"<Article {self.title} ({self.url})>"

    def get_content(self):
        return self.content if self.source_id is None else self.source.get_content()

    def update_content(self, session, content=None, commit=True):
        from zeeguu.core.content_retriever import download_and_parse
        from zeeguu.core.model.source import Source
        from zeeguu.core.model.source_type import SourceType
        from zeeguu.core.content_quality.quality_filter import (
            sufficient_quality_plain_text,
        )

        if content is None:
            content = download_and_parse(self.url.as_string()).text

            quality, reason, _ = sufficient_quality_plain_text(self.content)
            if not quality:
                print("Marking as broken. Reason: " + reason)
                self.mark_as_low_quality_and_remove_from_index()

        source = Source.find_or_create(
            session,
            content,
            SourceType.find_by_type(SourceType.ARTICLE),
            self.language,
            self.broken,
            commit=False,
        )
        self.source_id = source.id
        self.source = source
        # Remove once migration is done.
        self.content = content

        session.add(self)
        if commit:
            session.commit()

    def vote_broken(self):
        # somebody could vote that this article is broken
        self.broken += 1

    def get_broken(self):
        # remember to remove self.broken after migration
        return self.broken if self.broken else self.source.broken

    def topics_as_string(self):
        topics = ""
        for topic in self.topics:
            topics += topic.topic.title + ", "
        return topics

    def topics_as_tuple(self):
        topics = []
        for topic in self.topics:
            if topic.topic.title == "" or topic.topic.title is None:
                continue
            topics.append((topic.topic.title, topic.origin_type))
        return topics

    def contains_any_of(self, keywords: list):
        for each in keywords:
            if self.title.find(each) >= 0:
                return True
        return False

    def update(self, db_session, language, content, htmlContent, title):
        self.language = language
        self.update_content(db_session, content, commit=False)
        self.title = title
        self.htmlContent = htmlContent
        self.summary = self.get_content()[:MAX_CHAR_COUNT_IN_SUMMARY]
        db_session.commit()

    def create_article_fragments(self, session):
        """
        Dummy implmentation which just creates paragraphs tags.
        The idea is that we parse the readability parse, and create the
        different tags as needed.
        """
        from zeeguu.core.model.article_fragment import ArticleFragment

        for i, paragraph in enumerate(self.source.get_content().split("\n\n")):
            ArticleFragment.find_or_create(
                session, self, paragraph.strip(), i, "p", commit=False
            )

    def get_fk_difficulty(self):
        if self.fk_difficulty:
            return self.fk_difficulty
        else:
            return self.source.fk_difficulty

    def get_word_count(self):
        if self.word_count:
            return self.word_count
        else:
            return self.source.word_count

    def article_info(self, with_content=False):
        """

            This is the data that is sent over the API
            to the Reader. Whatever the reader needs
            must be here.

        :return:
        """

        summary = self.get_content()[:MAX_CHAR_COUNT_IN_SUMMARY]
        fk_difficulty = self.get_fk_difficulty()
        result_dict = dict(
            id=self.id,
            source_id=self.source_id,
            title=self.title,
            summary=summary,
            language=self.language.code,
            topics=self.topics_as_string(),
            topics_list=self.topics_as_tuple(),
            video=False,
            metrics=dict(
                difficulty=fk_difficulty / 100,
                word_count=self.get_word_count(),
                cefr_level=fk_to_cefr(fk_difficulty),
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
        if self.img_url:
            result_dict["img_url"] = self.img_url.as_string()

        if self.published_time:
            result_dict["published"] = datetime_to_json(self.published_time)

        if self.feed:
            # Is this supposed to be a tuple?
            result_dict["feed_id"] = (self.feed.id,)
            result_dict["feed_icon_name"] = self.feed.icon_name

            # TO DO: remove feed_image_url from RSSFeed --- this is here for compatibility
            # until the codebase is moved to zorg.
            if self.feed.image_url:
                result_dict["feed_image_url"] = self.feed.image_url.as_string()

        if with_content:
            from zeeguu.core.model.bookmark_context import ContextIdentifier
            from zeeguu.core.model.context_type import ContextType

            from zeeguu.core.model.article_fragment import ArticleFragment
            from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

            tokenizer = get_tokenizer(self.language, TOKENIZER_MODEL)
            content = self.get_content()
            result_dict["content"] = content
            result_dict["htmlContent"] = self.htmlContent
            result_dict["paragraphs"] = tokenizer.split_into_paragraphs(content)
            result_dict["tokenized_paragraphs"] = tokenizer.tokenize_text(
                content, flatten=False
            )
            result_dict["tokenized_fragments"] = []

            for fragment in ArticleFragment.get_all_article_fragments_in_order(self.id):
                result_dict["tokenized_fragments"].append(
                    {
                        "context_identifier": ContextIdentifier(
                            ContextType.ARTICLE_FRAGMENT,
                            article_fragment_id=fragment.id,
                        ).as_dictionary(),
                        "formatting": fragment.formatting,
                        "tokens": tokenizer.tokenize_text(
                            fragment.text.content, flatten=False
                        ),
                    }
                )

            ## TO-DO : Update once migration is complete.
            result_dict["tokenized_title_new"] = {
                "context_identifier": ContextIdentifier(
                    ContextType.ARTICLE_TITLE,
                    article_id=self.id,
                ).as_dictionary(),
                "tokens": tokenizer.tokenize_text(self.title, flatten=False),
            }
            result_dict["tokenized_title"] = tokenizer.tokenize_text(
                self.title, flatten=False
            )

        result_dict["has_uploader"] = True if self.uploader_id else False

        return result_dict

    def article_info_for_teacher(self):
        from zeeguu.core.model import CohortArticleMap

        info = self.article_info()
        info["cohorts"] = CohortArticleMap.get_cohorts_for_article(self)

        return info

    def is_owned_by(self, user):
        return self.uploader_id == user.id

    def add_or_replace_topic(self, topic, session, origin_type: TopicOriginType):
        t = ArticleTopicMap.create_or_update(
            article=self, topic=topic, origin_type=origin_type
        )
        session.add(t)

    def add_topic_if_doesnt_exist(self, topic, session, origin_type: TopicOriginType):
        t = ArticleTopicMap.create_if_doesnt_exists(
            article=self, topic=topic, origin_type=origin_type
        )
        session.add(t)

    def recalculate_topics_from_url_keywords(self, session):
        topics = []
        for url_keyword in self.url_keywords:
            topic = url_keyword.url_keyword.topic
            if topic is None:
                continue
            if topic in topics:
                continue
            topics.append(topic)
        self.add_topics_from_url_keyword(topics, session)

    def add_topics_from_url_keyword(self, topics, session):
        for topic in topics:
            t = ArticleTopicMap.create_or_update(
                article=self, topic=topic, origin_type=TopicOriginType.URL_PARSED
            )
            session.add(t)

    def add_url_keyword(self, url_keyword, rank, session):
        a = ArticleUrlKeywordMap(article=self, url_keyword=url_keyword, rank=rank)
        session.add(a)

    def set_url_keywords(self, url_keywords, session):
        for rank, t in enumerate(url_keywords):
            self.add_url_keyword(t, rank, session)

    def set_as_broken(self, session, broken_code):
        from zeeguu.core.model.article_broken_code_map import ArticleBrokenMap

        article_broken_map = ArticleBrokenMap.find_or_create(session, self, broken_code)
        self.broken = MARKED_BROKEN_DUE_TO_LOW_QUALITY
        if self.source:
            self.source.broken = MARKED_BROKEN_DUE_TO_LOW_QUALITY
        session.add(article_broken_map)
        session.add(self)
        session.commit()

    def add_search(self, search):
        self.searches.append(search)

    def remove_search(self, search):
        print("trying to remove a search term")
        self.searches.remove(search)

    def star_for_user(self, session, user, state=True):
        from zeeguu.core.model.user_article import UserArticle

        ua = UserArticle.find_or_create(session, user, self)
        ua.set_starred(state)
        session.add(ua)

    def mark_as_low_quality_and_remove_from_index(self):
        self.broken = MARKED_BROKEN_DUE_TO_LOW_QUALITY
        # if it was in ES, we delete it
        from zeeguu.core.elastic.indexing import remove_from_index

        remove_from_index(self)

    @classmethod
    def own_texts_for_user(cls, user, ignore_deleted=True):
        query = cls.query.filter(cls.uploader_id == user.id)

        if ignore_deleted:
            # by using > 0 we filter out both NULL and 0 values
            query = query.filter((cls.deleted == 0) | (cls.deleted.is_(None)))

        query = query.order_by(cls.id.desc())

        return query.all()

    @classmethod
    def create_clone(cls, session, source, uploader):
        # TODO: Why does this NOP the url?
        current_time = datetime.now()
        new_article = Article(
            None,
            source.title,
            None,
            source.source,
            source.summary,
            current_time,
            None,
            source.language,
            source.htmlContent,
            uploader,
        )
        session.add(new_article)

        session.commit()
        return new_article.id

    @classmethod
    def create_from_upload(
        cls, session, title, content, htmlContent, uploader, language
    ):
        current_time = datetime.now()

        # Create a Source object for the uploaded content
        source_type = SourceType.find_by_type(SourceType.ARTICLE)
        source = Source.find_or_create(
            session,
            content,
            source_type,
            language,
            0,  # broken flag
        )

        new_article = Article(
            None,
            title,
            None,
            source,  # Pass the Source object instead of raw content
            None,
            current_time,
            None,
            language,
            htmlContent,
            uploader,
        )
        session.add(new_article)

        session.commit()
        return new_article.id

    @classmethod
    def find_or_create(
        cls,
        session,
        url: str,
        html_content=None,
        title=None,
        authors: str = "",
    ):
        """

        If article for url found, return ID

        If not found,
            - if htmlContent is present, create article for that
            - if not, download and create article then return
        """
        from zeeguu.core.model import Url, Language
        from zeeguu.core.model.source import Source
        from zeeguu.core.model.source_type import SourceType

        from zeeguu.core.content_retriever.article_downloader import (
            extract_article_image,
            add_topics,
            add_url_keywords,
        )

        canonical_url = Url.extract_canonical_url(url)

        found = cls.find(canonical_url)
        if found:
            return found

        from zeeguu.core.content_retriever import readability_download_and_parse

        np_article = readability_download_and_parse(canonical_url)

        html_content = np_article.htmlContent
        summary = np_article.summary
        title = np_article.title
        authors = ", ".join(np_article.authors or [])
        lang = np_article.meta_lang

        language = Language.find(lang)

        # Create new article and save it to DB
        url_object = Url.find_or_create(session, canonical_url)
        source_type = SourceType.find_by_type(SourceType.ARTICLE)

        source = Source.find_or_create(
            session,
            np_article.text,
            source_type,
            language,
            0,
        )

        new_article = Article(
            url_object,
            title,
            authors,
            source,
            summary,
            datetime.now(),
            None,
            language,
            html_content,
        )
        # Remove once migration is complete

        session.add(new_article)

        new_article.create_article_fragments(session)

        main_img_url = extract_article_image(np_article)
        if main_img_url != "":
            new_article.img_url = Url.find_or_create(session, main_img_url)

        url_keywords = add_url_keywords(new_article, session)
        add_topics(new_article, None, url_keywords, session)

        session.add(new_article)
        session.commit()
        return new_article

    @classmethod
    def find_by_id(cls, id: int):
        return Article.query.filter(Article.id == id).first()

    @classmethod
    def find_by_source_id(cls, source_id: int):
        return Article.query.filter(Article.source_id == source_id).first()

    @classmethod
    def uploaded_by(cls, uploader_id: int):
        return Article.query.filter(Article.uploader_id == uploader_id).all()

    @classmethod
    def find(cls, url: str):
        """

            Find by url

        :return: object or None if not found
        """

        from zeeguu.core.model import Url

        try:
            url_object = Url.find(url)
            return (cls.query.filter(cls.url == url_object)).one()
        except NoResultFound:
            return None

    @classmethod
    def all_older_than(cls, days, limit=None):
        import datetime

        today = datetime.date.today()
        long_ago = today - datetime.timedelta(days)
        query = cls.query.filter(cls.published_time < long_ago).order_by(desc(cls.id))
        if limit:
            query = query.limit(limit)
        try:
            return query.all()

        except NoResultFound:
            return []

    @classmethod
    def all_younger_than(cls, days):
        import datetime

        today = datetime.date.today()
        some_time_ago = today - datetime.timedelta(days)
        try:
            return cls.query.filter(cls.published_time > some_time_ago).all()

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
