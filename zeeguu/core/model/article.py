import re
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    UnicodeText,
    desc,
    Enum,
    BigInteger,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.types import TypeDecorator

from zeeguu.core.language.ml_cefr_classifier import predict_cefr_level
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.article_topic_map import ArticleTopicMap
from zeeguu.core.model.article_topic_map import TopicOriginType
from zeeguu.core.model.article_url_keyword_map import ArticleUrlKeywordMap
from zeeguu.core.model.db import db
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.logging import log

MAX_CHAR_COUNT_IN_SUMMARY = 300
MARKED_BROKEN_DUE_TO_LOW_QUALITY = 100

HTML_TAG_CLEANR = re.compile("<[^>]*>")

MULTIPLE_NEWLINES = re.compile(r"\n\s*\n")


class UnsignedBigInteger(TypeDecorator):
    """Handles unsigned 64-bit integers for both MySQL and SQLite."""

    impl = BigInteger
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(BIGINT(unsigned=True))
        else:
            # SQLite doesn't have unsigned, store as string to avoid overflow
            return dialect.type_descriptor(String(20))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name != "mysql":
            # Convert to string for SQLite
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name != "mysql":
            # Convert back to int from string for SQLite
            return int(value) if value else None
        return value


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
    content_simhash = Column(UnsignedBigInteger)

    # Simplified article relationship fields
    parent_article_id = Column(Integer, ForeignKey("article.id"))
    # this is at the moment populated by an LLM
    cefr_level = Column(Enum("A1", "A2", "B1", "B2", "C1", "C2"))
    simplification_ai_generator_id = Column(Integer, ForeignKey("ai_generator.id"))

    # Self-referential relationship for simplified versions
    parent_article = relationship(
        "Article", remote_side=[id], backref="simplified_versions"
    )

    # Relationship to AI model used for simplification
    simplification_ai_generator = relationship(
        "AIGenerator", foreign_keys=[simplification_ai_generator_id]
    )

    # 1:1 relationship to CEFR assessment data
    cefr_assessment = relationship(
        "ArticleCefrAssessment",
        back_populates="article",
        uselist=False,  # 1:1 relationship
        cascade="all, delete-orphan",
    )

    # 1:1 relationship to tokenization cache
    tokenization_cache = relationship(
        "ArticleTokenizationCache",
        back_populates="article",
        uselist=False,  # 1:1 relationship
        cascade="all, delete-orphan",
    )

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

    # Articles that are too long might be extraction errors
    # or could cost too much in API calls for processing
    MAXIMUM_WORD_COUNT = 10000

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
        from zeeguu.core.model.article_fragment import ArticleFragment
        from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache

        self.language = language
        self.update_content(db_session, content, commit=False)
        self.title = title
        self.htmlContent = htmlContent
        self.summary = self.get_content()[:MAX_CHAR_COUNT_IN_SUMMARY]

        # Delete existing fragments
        ArticleFragment.query.filter_by(article_id=self.id).delete()

        # Invalidate tokenization cache since content/title/summary changed
        ArticleTokenizationCache.query.filter_by(article_id=self.id).delete()

        # Recreate fragments with updated content
        self.create_article_fragments(db_session)

        db_session.commit()

    def create_article_fragments(self, session):
        """
        Parse HTML content and create article fragments for each HTML element.
        This preserves the structure and formatting from the original article.
        """
        from zeeguu.core.model.article_fragment import ArticleFragment
        from bs4 import BeautifulSoup

        # Get HTML content - use htmlContent if available, otherwise fall back to plain text
        html_content = getattr(self, "htmlContent", None) or self.source.get_content()

        if not html_content:
            return

        # Parse HTML content
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract text content from HTML elements and create fragments
        order = 0
        # Include block-level HTML elements: headings, paragraphs, list items, blockquotes
        # Note: We skip ul/ol containers to avoid duplication, only process individual li items
        # Note: We skip inline elements like strong, em here as they should be preserved within their parent blocks
        block_elements = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]

        for element in soup.find_all(block_elements):
            # Skip blockquote containers - we'll process their paragraph children instead
            if element.name == "blockquote":
                continue

            # For paragraphs inside blockquotes, use special formatting to indicate they're part of a quote
            if element.name == "p" and element.find_parent("blockquote"):
                tag_name = "blockquote"
                text_content = element.get_text().strip()
            # For list items, get direct text content (not nested lists)
            elif element.name == "li":
                # Get only direct text content, excluding nested ul/ol
                text_parts = []
                for content in element.contents:
                    if hasattr(content, "get_text"):
                        # Skip nested lists
                        if content.name not in ["ul", "ol"]:
                            text_parts.append(content.get_text().strip())
                    else:
                        # Direct text node
                        text_parts.append(str(content).strip())
                text_content = " ".join(text_parts).strip()
                tag_name = element.name
            else:
                # For other elements, preserve some inline formatting by getting inner HTML
                # and then extracting text, but keep track of formatting
                text_content = element.get_text().strip()
                tag_name = element.name

            if text_content:  # Only create fragments for non-empty content
                ArticleFragment.find_or_create(
                    session, self, text_content, order, tag_name, commit=False
                )
                order += 1

        # If no HTML elements found, fall back to splitting plain text
        if order == 0:
            for i, paragraph in enumerate(self.source.get_content().split("\n\n")):
                paragraph_text = paragraph.strip()
                if paragraph_text:
                    ArticleFragment.find_or_create(
                        session, self, paragraph_text, i, "p", commit=False
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

        # Use stored summary if available, otherwise fallback to content truncation
        if self.summary and len(self.summary.strip()) > 10:
            summary = self.summary
        else:
            summary = self.get_content()[:MAX_CHAR_COUNT_IN_SUMMARY]
        fk_difficulty = self.get_fk_difficulty()

        # Use effective_cefr_level from assessment table (SINGLE SOURCE OF TRUTH)
        # Fallback to legacy article.cefr_level only if assessment doesn't exist
        if self.cefr_assessment and self.cefr_assessment.effective_cefr_level:
            cefr_level = self.cefr_assessment.effective_cefr_level
        else:
            # Legacy fallback
            cefr_level = self.cefr_level

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
                cefr_level=cefr_level,
            ),
        )

        # Add simplified article metadata if this is a simplified version
        if self.parent_article_id:
            result_dict["parent_article_id"] = self.parent_article_id
            # Include parent article's CEFR level
            if self.parent_article and self.parent_article.cefr_level:
                result_dict["parent_cefr_level"] = self.parent_article.cefr_level
            # Include parent URL for reference
            if self.parent_article and self.parent_article.url:
                result_dict["parent_url"] = self.parent_article.url.as_string()

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
            from zeeguu.core.model.context_identifier import ContextIdentifier
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

        # Add uploader name for classroom articles (so students can see who shared the text)
        if self.uploader:
            result_dict["uploader_name"] = self.uploader.name

        return result_dict

    def article_info_for_teacher(self):
        from zeeguu.core.model import CohortArticleMap

        info = self.article_info(with_content=True)
        info["cohorts"] = CohortArticleMap.get_cohorts_for_article(self)

        # Include CEFR assessment details for teacher view
        if self.cefr_assessment:
            info["cefr_assessments"] = {
                "llm": {
                    "level": self.cefr_assessment.llm_cefr_level,
                    "method": self.cefr_assessment.llm_method,
                    "assessed_at": self.cefr_assessment.llm_assessed_at.isoformat() if self.cefr_assessment.llm_assessed_at else None,
                },
                "ml": {
                    "level": self.cefr_assessment.ml_cefr_level,
                    "method": self.cefr_assessment.ml_method,
                    "assessed_at": self.cefr_assessment.ml_assessed_at.isoformat() if self.cefr_assessment.ml_assessed_at else None,
                },
                "teacher": {
                    "level": self.cefr_assessment.teacher_cefr_level,
                    "method": self.cefr_assessment.teacher_method,
                    "assessed_at": self.cefr_assessment.teacher_assessed_at.isoformat() if self.cefr_assessment.teacher_assessed_at else None,
                },
                "effective_cefr_level": self.cefr_assessment.effective_cefr_level,
                # Keep display_cefr for backward compatibility
                "display_cefr": self.cefr_assessment.effective_cefr_level,
                "simplification_target_level": self.cefr_assessment.simplification_target_level,
            }
        else:
            # Fallback for articles without assessment records yet
            info["cefr_assessments"] = {
                "llm": {
                    "level": self.cefr_level,
                    "method": None,
                    "assessed_at": None,
                },
                "ml": {
                    "level": None,
                    "method": None,
                    "assessed_at": None,
                },
                "teacher": {
                    "level": None,
                    "method": None,
                    "assessed_at": None,
                },
                "effective_cefr_level": self.cefr_level,
                # Keep display_cefr for backward compatibility
                "display_cefr": self.cefr_level,
            }

        return info

    def is_owned_by(self, user):
        return self.uploader_id == user.id

    def get_appropriate_version_for_user_level(self, user_cefr_level):
        """
        Returns the appropriate article version for the user's CEFR level.
        Supports compound levels: B1 user can read "B1/B2" articles.
        Falls back to original if no simplified version exists.
        """
        if not user_cefr_level:
            return self

        def matches_user_level(article):
            """Check if article matches user level (using assessment table as source of truth)."""
            # Get effective level from assessment table (source of truth)
            if article.cefr_assessment and article.cefr_assessment.effective_cefr_level:
                article_level = article.cefr_assessment.effective_cefr_level
            else:
                # Legacy fallback
                article_level = article.cefr_level

            if not article_level:
                return False

            # Exact match
            if article_level == user_cefr_level:
                return True

            # Compound level match: "B1/B2" matches both B1 and B2 users
            if "/" in article_level:
                lower, upper = article_level.split("/")
                return user_cefr_level in [lower, upper]

            return False

        # If this is already a simplified version, check if it matches
        if self.parent_article_id:
            if matches_user_level(self):
                return self
            else:
                # Delegate to parent article to find the right version
                return self.parent_article.get_appropriate_version_for_user_level(
                    user_cefr_level
                )

        # Look for simplified version matching user's level
        for simplified in self.simplified_versions:
            if matches_user_level(simplified):
                return simplified

        # Fallback to original article
        return self

    @classmethod
    def create_simplified_version(
        cls,
        session,
        parent_article,
        simplified_title,
        simplified_content,
        simplified_summary,
        cefr_level,
        ai_model,
        original_cefr_level=None,
        original_summary=None,
        commit=True,
    ):
        """
        Creates a simplified version of an article as a new entry in the article table
        """
        from zeeguu.core.model.source import Source
        from zeeguu.core.model.source_type import SourceType

        # Create a Source object for the simplified content
        source_type = SourceType.find_by_type(SourceType.ARTICLE)
        simplified_source = Source.find_or_create(
            session,
            simplified_content,
            source_type,
            parent_article.language,
            0,  # broken flag
            commit=False,
        )

        # Create temporary placeholder URL for simplified article
        # We'll update this to the standard format after the article gets its ID
        from zeeguu.core.model.url import Url
        import uuid

        placeholder_url_string = f"https://zeeguu.org/simplified/pending/{uuid.uuid4()}"
        placeholder_url = Url.find_or_create(session, placeholder_url_string)

        # Create the simplified article
        # Check if content is already HTML (from SimplificationService) or needs conversion
        simplified_html = ""
        if simplified_content:
            # If content starts with HTML tags, it's already been converted
            if simplified_content.strip().startswith("<"):
                simplified_html = simplified_content
            else:
                # Convert markdown/plain text to HTML
                import markdown2

                simplified_html = markdown2.markdown(
                    simplified_content,
                    extras=["break-on-newline", "fenced-code-blocks", "tables"],
                )

        simplified_article = cls(
            placeholder_url,  # Temporary placeholder URL
            simplified_title,
            "",  # Empty authors field for simplified articles
            simplified_source,
            simplified_summary,  # Use AI-generated summary
            parent_article.published_time,
            parent_article.feed,
            parent_article.language,
            simplified_html,  # Use generated HTML from simplified content
            parent_article.uploader,
        )

        # Debug: Ensure summary is set correctly
        if simplified_summary and len(simplified_summary) > 10:
            simplified_article.summary = simplified_summary
            log(
                f"Set simplified summary ({len(simplified_summary)} chars): {simplified_summary[:100]}..."
            )

        # Set simplified article specific fields
        simplified_article.parent_article_id = parent_article.id
        simplified_article.cefr_level = cefr_level

        # Find or create AI model record
        ai_generator_record = AIGenerator.find_or_create(session, ai_model)
        simplified_article.simplification_ai_generator_id = ai_generator_record.id

        # Inherit image from parent article
        if parent_article.img_url:
            simplified_article.img_url = parent_article.img_url

        # Set the original article's CEFR level and summary if provided and not already set
        if original_cefr_level and not parent_article.cefr_level:
            parent_article.cefr_level = original_cefr_level
            session.add(parent_article)

        if original_summary:
            parent_article.summary = original_summary
            session.add(parent_article)

        session.add(simplified_article)

        # Inherit topics from parent article with same origin type
        for topic_map in parent_article.topics:
            simplified_article.add_topic_if_doesnt_exist(
                topic_map.topic, session, topic_map.origin_type
            )

        # Create article fragments for web display
        simplified_article.create_article_fragments(session)

        if commit:
            session.commit()

            # Update URL to standard format now that we have the article ID
            final_url_string = (
                f"https://zeeguu.org/read/article?id={simplified_article.id}"
            )
            final_url = Url.find_or_create(session, final_url_string)
            simplified_article.url = final_url
            session.add(simplified_article)  # Ensure the updated article is tracked
            session.commit()

            # Create assessment record for simplified article
            from zeeguu.core.model import ArticleCefrAssessment

            simplified_assessment = ArticleCefrAssessment.find_or_create(
                session, simplified_article.id, commit=False
            )

            # Store what level we asked LLM to simplify TO (might differ from actual measured level)
            # Note: We don't set llm_cefr_level here because that would conflate target with measurement
            # The ML assessment below will provide the actual measured difficulty
            simplified_assessment.simplification_target_level = cefr_level

            # ALWAYS run ML assessment on simplified text to verify actual difficulty
            # This lets us detect when simplification didn't work as intended
            try:
                ml_level = predict_cefr_level(
                    simplified_article.get_content(),
                    simplified_article.language.code,
                    simplified_article.get_fk_difficulty(),
                    simplified_article.get_word_count(),
                )
                if ml_level:
                    simplified_assessment.set_ml_assessment(ml_level, "ml")
                    log(f"Simplified article {simplified_article.id}: Target={cefr_level}, ML measured={ml_level}")
            except Exception as e:
                log(f"Failed to run ML assessment on simplified article {simplified_article.id}: {e}")

            session.add(simplified_assessment)
            session.commit()

            # Refresh to ensure we have the latest state
            session.refresh(simplified_article)

        return simplified_article

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
        """
        Clone an existing article for a new uploader (e.g., teacher sharing with another teacher).

        Uses create_from_upload() to avoid code duplication, then copies the detailed
        assessment records (both LLM and ML) from the source article.
        """
        # Get image URL as string if it exists
        img_url_string = source.img_url.as_string() if source.img_url else None

        # Create article using create_from_upload, preserving the original CEFR level
        # This will run ML assessment but preserve LLM assessment from source
        new_article_id = cls.create_from_upload(
            session,
            title=source.title,
            content=source.get_content(),
            htmlContent=source.htmlContent,
            uploader=uploader,
            language=source.language,
            original_cefr_level=source.cefr_level,  # Preserve existing assessment
            img_url=img_url_string,
        )

        # Now copy the detailed assessment records from source (both LLM and ML methods)
        # This ensures we preserve the assessment provenance (which LLM was used, etc.)
        if source.cefr_assessment:
            from zeeguu.core.model import ArticleCefrAssessment

            cloned_assessment = ArticleCefrAssessment.find_or_create(
                session, new_article_id, commit=False
            )

            # Copy LLM assessment (overwrite what create_from_upload set)
            if source.cefr_assessment.llm_cefr_level:
                cloned_assessment.set_llm_assessment(
                    source.cefr_assessment.llm_cefr_level,
                    source.cefr_assessment.llm_method,
                )

            # Copy ML assessment (overwrite fresh ML assessment from create_from_upload)
            if source.cefr_assessment.ml_cefr_level:
                cloned_assessment.set_ml_assessment(
                    source.cefr_assessment.ml_cefr_level,
                    source.cefr_assessment.ml_method,
                )

            # Don't copy teacher override (new article shouldn't inherit manual overrides)

            session.add(cloned_assessment)
            session.commit()

        return new_article_id

    @classmethod
    def create_from_upload(
        cls,
        session,
        title,
        content,
        htmlContent,
        uploader,
        language,
        original_cefr_level=None,
        img_url=None,
    ):
        from zeeguu.core.content_cleaning import cleanup_text

        current_time = datetime.now()

        # Clean the content to ensure Source text is plain text without HTML
        clean_content = cleanup_text(content)

        # Create a Source object for the uploaded content
        source_type = SourceType.find_by_type(SourceType.ARTICLE)
        source = Source.find_or_create(
            session,
            clean_content,
            source_type,
            language,
            0,  # broken flag
        )

        new_article = Article(
            None,
            title,
            None,
            source,
            None,
            current_time,
            None,
            language,
            htmlContent,
            uploader,
        )

        # Set image URL if provided (when cloning)
        if img_url:
            from zeeguu.core.model.url import Url

            # Validate that img_url is actually a URL, not HTML content
            if img_url.startswith(('http://', 'https://')):
                new_article.img_url = Url.find_or_create(session, img_url)
            else:
                log(f"Invalid img_url format (not a URL): {img_url[:100]}...")

        session.add(new_article)
        session.commit()

        # Create article fragments for reader tokenization
        new_article.create_article_fragments(session)

        session.commit()

        # Assess CEFR level using both LLM and ML
        from zeeguu.core.model import ArticleCefrAssessment

        llm_level = None
        ml_level = None

        if original_cefr_level:
            # Preserve original level as LLM assessment
            llm_level = original_cefr_level
            new_article.cefr_level = original_cefr_level
        else:
            # LLM assessment using DeepSeek
            try:
                from zeeguu.core.llm_services.simplification_and_classification import (
                    assess_article_cefr_level_deepseek_only,
                )

                llm_level = assess_article_cefr_level_deepseek_only(
                    title, content, language.code
                )
                if llm_level:
                    new_article.cefr_level = llm_level
            except Exception as e:
                print(f"Could not assess CEFR level with LLM for uploaded article: {e}")

        # ML assessment
        try:
            ml_level = predict_cefr_level(
                new_article.get_content(),
                language.code,
                new_article.get_fk_difficulty(),
                new_article.get_word_count(),
            )
        except Exception as e:
            print(f"Could not assess CEFR level with ML for uploaded article: {e}")

        # Create assessment record with both LLM and ML assessments
        if llm_level or ml_level:
            assessment = ArticleCefrAssessment.find_or_create(
                session, new_article.id, commit=False
            )

            if llm_level:
                assessment.set_llm_assessment(llm_level, "llm_assessed_deepseek")
            if ml_level:
                # ML model successfully predicted a level
                assessment.set_ml_assessment(ml_level, "ml")

            session.add(assessment)
            session.commit()

        # Log after commit when ID is available
        if original_cefr_level:
            print(
                f"Preserved original CEFR level {original_cefr_level} for copied article {new_article.id}"
            )
        elif new_article.cefr_level:
            print(
                f"DeepSeek assessed uploaded article {new_article.id} as {new_article.cefr_level} level"
            )
        return new_article.id

    def assess_cefr_level(self, session):
        """
        Assess article CEFR level using both LLM (fallback chain) and ML classifiers.

        This is a separate method to follow single responsibility principle - article
        creation and assessment are independent concerns.

        Updates:
            - self.cefr_level: Set to LLM assessment if available
            - ArticleCefrAssessment record: Creates/updates with both LLM and ML results

        Returns:
            None (modifies article and database in place)
        """
        from zeeguu.core.model import ArticleCefrAssessment

        llm_level = None
        llm_method = None
        ml_level = None

        # LLM assessment (with fallback chain: Anthropic → DeepSeek)
        try:
            from zeeguu.core.llm_services.simplification_and_classification import (
                assess_article_cefr_level,
            )

            llm_level, llm_method = assess_article_cefr_level(
                self.title, self.get_content(), self.language.code
            )
            if llm_level:
                self.cefr_level = llm_level
                log(
                    f"LLM assessed article {self.id} as {llm_level} level (method: {llm_method})"
                )
        except Exception as e:
            log(f"Failed to assess CEFR level with LLM for article {self.id}: {str(e)}")

        # ML assessment (fast, always try)
        try:
            ml_level = predict_cefr_level(
                self.get_content(),
                self.language.code,
                self.get_fk_difficulty(),
                self.get_word_count(),
            )
            if ml_level:
                log(f"ML assessed article {self.id} as {ml_level} level")
        except Exception as e:
            log(f"Failed to assess CEFR level with ML for article {self.id}: {str(e)}")

        # Create assessment record with both LLM and ML assessments
        if llm_level or ml_level:
            assessment = ArticleCefrAssessment.find_or_create(
                session, self.id, commit=False
            )

            if llm_level:
                assessment.set_llm_assessment(llm_level, llm_method)
            if ml_level:
                assessment.set_ml_assessment(ml_level, "ml")

            session.add(assessment)
            session.commit()

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
        Find existing article by URL or create new article from URL.

        Note: This method does NOT assess CEFR level. Call article.assess_cefr_level(session)
        separately if needed (e.g., for user-initiated article reading).

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

        session.add(new_article)

        new_article.create_article_fragments(session)

        main_img_url = extract_article_image(np_article)
        if main_img_url and main_img_url != "":
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
    def find_by_content_and_source(
        cls, title: str, content_preview: str, feed_id: int, language_id: int
    ):
        """
        Find existing article by content fingerprint and source to prevent duplicates.
        This is a fallback when URL-based deduplication fails.

        Args:
            title: Article title
            content_preview: First 1000 characters of article content
            feed_id: Feed ID
            language_id: Language ID

        Returns:
            Article object if duplicate found, None otherwise
        """
        try:
            # First try exact title match
            exact_match = cls.query.filter(
                cls.title == title,
                cls.content.like(f"{content_preview}%"),
                cls.feed_id == feed_id,
                cls.language_id == language_id,
                cls.parent_article_id == None,
            ).first()

            if exact_match:
                return exact_match

            # If no exact match, try fuzzy title matching for similar titles
            # This catches typos like "Gittes Von G" vs "Gitte Von G"
            import difflib

            # Get all articles from same feed with similar content length
            candidates = cls.query.filter(
                cls.content.like(f"{content_preview}%"),
                cls.feed_id == feed_id,
                cls.language_id == language_id,
                cls.parent_article_id == None,
            ).all()

            # Check for similar titles using fuzzy matching
            for candidate in candidates:
                if candidate.title and title:
                    # Calculate similarity ratio (0.0 to 1.0)
                    similarity = difflib.SequenceMatcher(
                        None, title.lower(), candidate.title.lower()
                    ).ratio()

                    # If titles are very similar (>90% match), consider it a duplicate
                    if similarity > 0.9:
                        log(
                            f"Found similar article: '{title}' vs '{candidate.title}' (similarity: {similarity:.3f})"
                        )
                        return candidate

            return None

        except Exception as e:
            # If anything goes wrong, don't block article creation
            log(f"Error in content-based deduplication: {str(e)}")
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

    def safe_delete(self, session, user):
        """
        Attempts to permanently delete an article if only the given user has interacted with it.
        If other users have interacted, just marks it as deleted.

        Returns True if permanently deleted, False if only marked as deleted.
        """
        from zeeguu.core.model import (
            UserArticle,
            PersonalCopy,
            UserReadingSession,
            UserActivityData,
            CohortArticleMap,
        )

        # Check if other users have interacted with this article
        should_permanently_delete = True

        # 1. Check UserReadingSession
        reading_sessions = UserReadingSession.query.filter_by(article_id=self.id).all()
        other_user_sessions = [rs for rs in reading_sessions if rs.user_id != user.id]
        if other_user_sessions:
            should_permanently_delete = False

        # 2. Check UserActivityData
        if should_permanently_delete and self.source_id:
            activity_data = UserActivityData.query.filter_by(
                source_id=self.source_id
            ).all()
            other_user_activity = [ad for ad in activity_data if ad.user_id != user.id]
            if other_user_activity:
                should_permanently_delete = False

        # 3. Check UserArticle
        if should_permanently_delete:
            user_articles = UserArticle.query.filter_by(article_id=self.id).all()
            other_user_articles = [ua for ua in user_articles if ua.user_id != user.id]
            if other_user_articles:
                should_permanently_delete = False

        # 4. Check PersonalCopy
        if should_permanently_delete:
            personal_copies = PersonalCopy.query.filter_by(article_id=self.id).all()
            other_user_copies = [pc for pc in personal_copies if pc.user_id != user.id]
            if other_user_copies:
                should_permanently_delete = False

        # 5. Check CohortArticleMap
        if should_permanently_delete:
            cohort_maps = CohortArticleMap.query.filter_by(article_id=self.id).all()
            if cohort_maps:
                should_permanently_delete = False

        if should_permanently_delete:
            # Safe to permanently delete - only this user has interacted with it

            # Remove this user's reading sessions
            for rs in reading_sessions:
                session.delete(rs)

            # Remove this user's activity data
            if self.source_id:
                activity_data = UserActivityData.query.filter_by(
                    source_id=self.source_id
                ).all()
                for ad in activity_data:
                    session.delete(ad)

            # Remove this user's article interactions
            user_articles = UserArticle.query.filter_by(article_id=self.id).all()
            for ua in user_articles:
                session.delete(ua)

            # Remove this user's personal copies
            personal_copies = PersonalCopy.query.filter_by(article_id=self.id).all()
            for pc in personal_copies:
                session.delete(pc)

            # Delete the article itself
            session.delete(self)
            session.commit()
            return True
        else:
            # Just mark as deleted - other users have interacted with it
            self.deleted = 1
            session.commit()
            CohortArticleMap.delete_all_for_article(session, self.id)
            return False
