from datetime import datetime

from sqlalchemy import (
    Column,
    UniqueConstraint,
    Integer,
    ForeignKey,
    DateTime,
    Boolean,
    Float,
    or_,
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import Article, User
from zeeguu.core.model.article_difficulty_feedback import ArticleDifficultyFeedback
from zeeguu.core.model.article_topic_user_feedback import ArticleTopicUserFeedback
from zeeguu.core.model.db import db
from zeeguu.core.model.personal_copy import PersonalCopy
from zeeguu.core.util.encoding import datetime_to_json
from zeeguu.logging import log


class UserArticle(db.Model):
    """

    A user and an article.
    It's simple.

    Did she open it?
    Did she like it?

    The kind of info that's in here.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    # Together an url_id and user_id are UNIQUE :)
    UniqueConstraint(article_id, user_id)

    # once an article has been opened, we display it
    # in a different way in the article list; we might
    # also, just as well not even show it anymore
    # we don't keep only the boolean here, since it is
    # more informative to have the time when opened;
    # could turn out to be useful for showing the
    # user reading history for example
    opened = Column(DateTime)

    # There's a star icon at the top of an article;
    # Reader can use it to mark the article in any way
    # they like.
    starred = Column(DateTime)

    # There's a button at the bottom of every article
    # this tracks the state of that button
    liked = Column(Boolean)

    # Store the current reading completion percentage (0.0 to 1.0)
    # Updated on every scroll event to avoid expensive recalculation
    reading_completion = Column(Float, default=0.0)

    # Track when the user completed reading the article (>90% threshold)
    # Also serves as a flag that notification was sent
    completed_at = Column(DateTime)

    # Hide article from user's feed
    # When set, article won't appear in recommendations
    hidden = Column(DateTime)

    def __init__(
        self,
        user,
        article,
        opened=None,
        starred=None,
        liked=None,
        reading_completion=0.0,
        completed_at=None,
        hidden=None,
    ):
        self.user = user
        self.article = article
        self.opened = opened
        self.starred = starred
        self.liked = liked
        self.reading_completion = reading_completion
        self.completed_at = completed_at
        self.hidden = hidden

    def __repr__(self):
        return f"{self.user} and {self.article}: Opened: {self.opened}, Starred: {self.starred}, Liked: {self.liked}"

    def user_info_as_string(self):
        return f"{self.user} Opened: {self.opened}, Starred: {self.starred}, Liked: {self.liked}"

    def set_starred(self, state=True):
        if state:
            self.starred = datetime.now()
        else:
            self.starred = None

    def set_opened(self, state=True):
        if state:
            self.opened = datetime.now()
        else:
            self.opened = None

    def set_liked(self, new_state=True):
        self.liked = new_state

    def set_hidden(self, state=True):
        if state:
            self.hidden = datetime.now()
        else:
            self.hidden = None

    def last_interaction(self):
        """

            sometimes we want to order articles based
            on this

        :return:
        """
        if self.opened:
            return self.opened
        if self.starred:
            return self.starred
        return None

    @classmethod
    def find_by_article(cls, article: Article):
        try:
            return cls.query.filter_by(article=article).all()
        except NoResultFound:
            return None

    @classmethod
    def find(cls, user: User, article: Article):
        """

        Retrieve existing object or None

        """

        return cls.query.filter_by(user=user, article=article).first()

    @classmethod
    def find_or_create(
        cls,
        session,
        user: User,
        article: Article,
        opened=None,
        liked=None,
        starred=None,
        reading_completion=0.0,
        completed_at=None,
        hidden=None,
    ):
        """

        create a new object and add it to the db if it's not already there
        otherwise retrieve the existing object and update

        """
        try:
            return cls.query.filter_by(user=user, article=article).one()
        except NoResultFound:
            try:
                new = cls(
                    user,
                    article,
                    opened=opened,
                    liked=liked,
                    starred=starred,
                    reading_completion=reading_completion,
                    completed_at=completed_at,
                    hidden=hidden,
                )
                session.add(new)
                session.commit()
                return new
            except Exception as e:
                from sentry_sdk import capture_exception

                capture_exception(e)
                print("seems we avoided a race condition")
                session.rollback()
                return cls.query.filter_by(user=user, article=article).one()

    @classmethod
    def all_starred_articles_of_user(cls, user):
        return (
            cls.query.filter_by(user=user)
            .filter(UserArticle.starred.isnot(None))
            .filter(UserArticle.hidden.is_(None))  # Exclude hidden articles
            .all()
        )

    @classmethod
    def all_liked_articles_of_user(cls, user):
        return (
            cls.query.filter_by(user=user).filter(UserArticle.liked.isnot(False)).all()
        )

    @classmethod
    def all_liked_articles_of_user_by_id(cls, user_id):
        return (
            cls.query.filter(UserArticle.user_id == user_id)
            .filter(UserArticle.liked == True)
            .all()
        )

    @classmethod
    def all_starred_or_liked_articles_of_user(cls, user, limit=30):
        return (
            cls.query.filter_by(user=user)
            .filter(
                or_(UserArticle.starred.isnot(None), UserArticle.liked.isnot(False))
            )
            .filter(UserArticle.hidden.is_(None))  # Exclude hidden articles
            .order_by(UserArticle.article_id.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def all_starred_articles_of_user_info(cls, user):
        """

            prepares info as it is promised by /get_starred_articles

        :param user:
        :return:
        """

        user_articles = cls.all_starred_articles_of_user(user)

        dicts = [
            dict(
                user_id=each.user.id,
                url=each.article.url.as_string(),
                title=each.article.title,
                language=each.article.language.code,
                starred_date=datetime_to_json(each.starred),
                starred=(each.starred != None),
                liked=each.liked,
            )
            for each in user_articles
        ]

        return dicts

    @classmethod
    def all_starred_and_liked_articles_of_user_info(cls, user):
        """

            prepares info as it is promised by /get_starred_articles

        :param user:
        :return:
        """

        user_articles = cls.all_starred_or_liked_articles_of_user(user)

        return [
            cls.user_article_info(
                user,
                cls.select_appropriate_article_for_user(user, each.article),
                with_translations=False,
            )
            for each in user_articles
            if each.last_interaction() is not None
        ]

    @classmethod
    def exists(cls, obj):
        try:
            cls.query.filter(cls.id == obj.id).one()
            return True
        except NoResultFound:
            return False

    @classmethod
    def filter_hidden_articles(cls, user, articles):
        """
        Filter out articles that are hidden by the user.
        Handles both regular articles and simplified articles with hidden parents.

        Args:
            user: The user object
            articles: List of Article objects to filter

        Returns:
            List of Article objects with hidden articles removed
        """
        filtered = []
        for article in articles:
            # Check if this article is hidden
            user_article = cls.find(user, article)
            if user_article and user_article.hidden:
                continue

            # If this is a simplified article, check if parent is hidden
            if article.parent_article_id:
                parent_user_article = cls.find(user, article.parent_article)
                if parent_user_article and parent_user_article.hidden:
                    continue

            filtered.append(article)

        return filtered

    @classmethod
    def filter_hidden_content(cls, user, content_list):
        """
        Filter out hidden articles from mixed content (articles and videos).
        Videos and other non-Article content types are preserved.

        Args:
            user: The user object
            content_list: List of content items (Articles, Videos, etc.)

        Returns:
            List of content items with hidden articles removed
        """
        from zeeguu.core.model import Article

        filtered = []
        for item in content_list:
            # Only filter Article objects, preserve other types
            if isinstance(item, Article):
                user_article = cls.find(user, item)
                if user_article and user_article.hidden:
                    continue

                # If this is a simplified article, check if parent is hidden
                if item.parent_article_id:
                    parent_user_article = cls.find(user, item.parent_article)
                    if parent_user_article and parent_user_article.hidden:
                        continue

                filtered.append(item)
            else:
                # Keep videos and other content types
                filtered.append(item)

        return filtered

    @classmethod
    def select_appropriate_article_for_user(
        cls, user: User, article: Article
    ) -> Article:
        """
        Selects the appropriate article version for a user based on their CEFR level.
        Used for recommendations, search results, and listings.
        """
        try:
            user_cefr_level = user.cefr_level_for_learned_language()
        except (AttributeError, IndexError, TypeError):
            user_cefr_level = None

        return article.get_appropriate_version_for_user_level(user_cefr_level)

    @classmethod
    def user_article_info(
        cls, user: User, article: Article, with_content=False, with_translations=True
    ):
        """
        Returns user-specific article information for the given article.
        No longer handles article selection - that should be done by the caller.

        Args:
            user: The user requesting the article info
            article: The article to get info for
            with_content: Whether to include full content/tokenization
            with_translations: Whether to include translation data
        """

        from zeeguu.core.model.bookmark import Bookmark
        from zeeguu.core.model.article_title_context import ArticleTitleContext
        from zeeguu.core.model.article_fragment_context import (
            ArticleFragmentContext,
        )

        # Initialize returned info with the article info
        # Use teacher version if user is a teacher (includes CEFR assessments)
        if user.isTeacher():
            returned_info = article.article_info_for_teacher()
            # Merge content if requested
            if with_content:
                content_info = article.article_info(with_content=True)
                returned_info.update(
                    {
                        k: v
                        for k, v in content_info.items()
                        if k.startswith("content")
                        or k.startswith("tokenized")
                        or k == "paragraphs"
                        or k == "htmlContent"
                    }
                )
        else:
            returned_info = article.article_info(with_content=with_content)
        user_article_info = UserArticle.find(user, article)
        user_diff_feedback = ArticleDifficultyFeedback.find(user, article)
        user_topics_feedback = ArticleTopicUserFeedback.find_given_user_article(
            article, user
        )
        if user_topics_feedback:
            article_topic_list = returned_info["topics_list"]
            topic_list = []
            topics_to_remove = set(
                [
                    untf.topic.title
                    for untf in user_topics_feedback
                    if untf.feedback == ArticleTopicUserFeedback.DO_NOT_SHOW_FEEDBACK
                ]
            )
            for each in article_topic_list:
                title, _ = each
                if title not in topics_to_remove:
                    topic_list.append(each)
            returned_info["topics_list"] = topic_list
            returned_info["topics"] = ",".join([t for t, _ in topic_list])

        if not user_article_info:
            returned_info["starred"] = False
            returned_info["opened"] = False
            returned_info["liked"] = None
            returned_info["hidden"] = False
            returned_info["reading_completion"] = 0.0
            returned_info["translations"] = []

        else:
            # Use stored reading completion - no more expensive calculations!
            returned_info["reading_completion"] = (
                user_article_info.reading_completion or 0.0
            )
            returned_info["starred"] = user_article_info.starred is not None
            returned_info["opened"] = user_article_info.opened is not None
            returned_info["liked"] = user_article_info.liked
            returned_info["hidden"] = user_article_info.hidden is not None
            if user_article_info.starred:
                returned_info["starred_time"] = datetime_to_json(
                    user_article_info.starred
                )

            if user_diff_feedback is not None:
                returned_info["relative_difficulty"] = (
                    user_diff_feedback.difficulty_feedback
                )

            if with_translations:
                translations = Bookmark.find_all_for_user_and_article(user, article)
                returned_info["translations"] = [
                    each.as_dictionary() for each in translations
                ]
            if "tokenized_fragments" in returned_info:
                for i, fragment in enumerate(returned_info["tokenized_fragments"]):
                    returned_info["tokenized_fragments"][i]["past_bookmarks"] = (
                        ArticleFragmentContext.get_all_user_bookmarks_for_article_fragment(
                            user.id,
                            fragment["context_identifier"]["article_fragment_id"],
                        )
                    )
            if "tokenized_title_new" in returned_info:
                returned_info["tokenized_title_new"]["past_bookmarks"] = (
                    ArticleTitleContext.get_all_user_bookmarks_for_article_title(
                        user.id, article.id
                    )
                )

        if PersonalCopy.exists_for(user, article):
            returned_info["has_personal_copy"] = True
        else:
            returned_info["has_personal_copy"] = False

        return returned_info

    @classmethod
    def user_article_summary_info(cls, user: User, article: Article):
        """
        Returns tokenized summary and title for an article with user bookmarks.
        This is a lightweight version of user_article_info that only processes
        the summary and title, not the full article content.

        Uses cached tokenization when available to avoid expensive Stanza processing.

        Args:
            user: The user requesting the article summary
            article: The article to get summary info for
        """
        import json
        from zeeguu.core.model.article_summary_context import ArticleSummaryContext
        from zeeguu.core.model.article_title_context import ArticleTitleContext
        from zeeguu.core.model.context_identifier import ContextIdentifier
        from zeeguu.core.model.context_type import ContextType
        from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL
        from . import db

        result = {
            "id": article.id,
            "language": article.language.code,
        }

        # Re-enabling with extensive logging to debug CPU accumulation
        import time
        start_time = time.time()
        log(f"[TOKENIZATION-START] Article {article.id} - Starting tokenization")

        # Get or create tokenization cache
        from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
        cache_start = time.time()
        cache = ArticleTokenizationCache.find_or_create(db.session, article)
        cache_time = time.time() - cache_start
        log(f"[TOKENIZATION-CACHE] Article {article.id} - Cache lookup took {cache_time:.3f}s")

        # Tokenize summary if available
        if article.summary:
            summary_context_id = ContextIdentifier(
                ContextType.ARTICLE_SUMMARY, article_id=article.id
            )

            # Try to use cached tokenization
            check_cache_start = time.time()
            if cache.tokenized_summary:
                try:
                    tokenized_summary = json.loads(cache.tokenized_summary)
                    log(f"[TOKENIZATION-SUMMARY] Article {article.id} - Using cached summary")
                except (json.JSONDecodeError, TypeError):
                    tokenized_summary = None
                    log(f"[TOKENIZATION-SUMMARY] Article {article.id} - Cache corrupt, will re-tokenize")
            else:
                tokenized_summary = None
                log(f"[TOKENIZATION-SUMMARY] Article {article.id} - No cache, will tokenize")

            # If no cache, tokenize and cache it
            if tokenized_summary is None:
                tokenizer_start = time.time()
                tokenizer = get_tokenizer(article.language, TOKENIZER_MODEL)
                tokenizer_get_time = time.time() - tokenizer_start
                log(f"[TOKENIZATION-SUMMARY] Article {article.id} - Got tokenizer in {tokenizer_get_time:.3f}s")

                tokenize_start = time.time()
                tokenized_summary = tokenizer.tokenize_text(article.summary, flatten=False)
                tokenize_time = time.time() - tokenize_start
                log(f"[TOKENIZATION-SUMMARY] Article {article.id} - Tokenized summary in {tokenize_time:.3f}s")

                json_start = time.time()
                cache.tokenized_summary = json.dumps(tokenized_summary)
                json_time = time.time() - json_start
                log(f"[TOKENIZATION-SUMMARY] Article {article.id} - JSON dumps took {json_time:.3f}s")

                db.session.add(cache)
                log(f"[TOKENIZATION-SUMMARY] Article {article.id} - Added cache to session")
                # Don't commit here - let Flask teardown handle it to avoid transaction conflicts

            bookmark_start = time.time()
            result["tokenized_summary"] = {
                "tokens": tokenized_summary,
                "context_identifier": summary_context_id.as_dictionary(),
                "past_bookmarks": ArticleSummaryContext.get_all_user_bookmarks_for_article_summary(
                    user.id, article.id
                ),
            }
            bookmark_time = time.time() - bookmark_start
            log(f"[TOKENIZATION-SUMMARY] Article {article.id} - Built result dict in {bookmark_time:.3f}s")

        # Tokenize title (always present)
        title_context_id = ContextIdentifier(
            ContextType.ARTICLE_TITLE, article_id=article.id
        )

        # Try to use cached tokenization
        if cache.tokenized_title:
            try:
                tokenized_title = json.loads(cache.tokenized_title)
                log(f"[TOKENIZATION-TITLE] Article {article.id} - Using cached title")
            except (json.JSONDecodeError, TypeError):
                tokenized_title = None
                log(f"[TOKENIZATION-TITLE] Article {article.id} - Cache corrupt, will re-tokenize")
        else:
            tokenized_title = None
            log(f"[TOKENIZATION-TITLE] Article {article.id} - No cache, will tokenize")

        # If no cache, tokenize and cache it
        if tokenized_title is None:
            tokenizer_start = time.time()
            tokenizer = get_tokenizer(article.language, TOKENIZER_MODEL)
            tokenizer_get_time = time.time() - tokenizer_start
            log(f"[TOKENIZATION-TITLE] Article {article.id} - Got tokenizer in {tokenizer_get_time:.3f}s")

            tokenize_start = time.time()
            tokenized_title = tokenizer.tokenize_text(article.title, flatten=False)
            tokenize_time = time.time() - tokenize_start
            log(f"[TOKENIZATION-TITLE] Article {article.id} - Tokenized title in {tokenize_time:.3f}s")

            json_start = time.time()
            cache.tokenized_title = json.dumps(tokenized_title)
            json_time = time.time() - json_start
            log(f"[TOKENIZATION-TITLE] Article {article.id} - JSON dumps took {json_time:.3f}s")

            db.session.add(cache)
            log(f"[TOKENIZATION-TITLE] Article {article.id} - Added cache to session")
            # Don't commit here - let Flask teardown handle it to avoid transaction conflicts

        bookmark_start = time.time()
        result["tokenized_title"] = {
            "tokens": tokenized_title,
            "context_identifier": title_context_id.as_dictionary(),
            "past_bookmarks": ArticleTitleContext.get_all_user_bookmarks_for_article_title(
                user.id, article.id
            ),
        }
        bookmark_time = time.time() - bookmark_start
        log(f"[TOKENIZATION-TITLE] Article {article.id} - Built result dict in {bookmark_time:.3f}s")

        total_time = time.time() - start_time
        log(f"[TOKENIZATION-END] Article {article.id} - Total tokenization took {total_time:.3f}s")

        return result
