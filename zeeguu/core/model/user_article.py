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
from zeeguu.core.model.user_mwe_override import UserMweOverride
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
        Prepares info as promised by /get_starred_articles
        """
        user_articles = cls.all_starred_or_liked_articles_of_user(user)

        # Filter first, then use helper for proper cache handling
        articles = [
            each.article
            for each in user_articles
            if each.last_interaction() is not None
        ]

        return cls.article_infos(user, articles, select_appropriate=True)

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
        cls, user: User, article: Article, with_content=False, with_translations=True, with_summary=True, tokenization_cache=None
    ):
        """
        Returns user-specific article information for the given article.
        No longer handles article selection - that should be done by the caller.

        Args:
            user: The user requesting the article info
            article: The article to get info for
            with_content: Whether to include full content/tokenization
            with_translations: Whether to include translation data
            with_summary: Whether to include tokenized summary/title (default True for homepage performance)
            tokenization_cache: Pre-fetched cache object (optional, avoids extra query)
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

        # Clear MWE metadata from tokens that user has disabled
        # This is done on backend to keep frontend simple (ADR 009)
        if with_content:
            overrides_by_hash = UserMweOverride.get_disabled_mwes_for_user_article(user.id, article.id)
            if overrides_by_hash and "tokenized_fragments" in returned_info:
                # Structure is: fragments -> tokens (paragraphs) -> sentences -> tokens
                for fragment in returned_info["tokenized_fragments"]:
                    for paragraph in fragment.get("tokens", []):
                        for sentence in paragraph:
                            if sentence:
                                # Compute sentence hash to check for overrides
                                sentence_text = " ".join(t.get("text", "") for t in sentence)
                                sentence_hash = UserMweOverride.compute_sentence_hash(sentence_text)
                                if sentence_hash in overrides_by_hash:
                                    disabled_expressions = overrides_by_hash[sentence_hash]
                                    # Clear MWE metadata from tokens matching disabled expressions
                                    cls._clear_mwe_metadata_for_expressions(sentence, disabled_expressions)

        # Include tokenized summary if requested (enabled by default for homepage performance)
        if with_summary and not with_content:
            # Only include summary if we're not already including full content
            # (full content tokenization includes everything)
            summary_info = cls.user_article_summary_info(user, article, tokenization_cache=tokenization_cache)
            # Merge summary-specific keys into the returned info
            # Map to frontend-expected keys for backwards compatibility
            if "tokenized_summary" in summary_info:
                returned_info["interactiveSummary"] = summary_info["tokenized_summary"]
            if "tokenized_title" in summary_info:
                returned_info["interactiveTitle"] = summary_info["tokenized_title"]

        return returned_info

    @staticmethod
    def _clear_mwe_metadata_for_expressions(sentence_tokens, disabled_expressions):
        """
        Clear MWE metadata from tokens that belong to disabled MWE expressions.

        Args:
            sentence_tokens: List of token dicts in a sentence
            disabled_expressions: List of MWE expressions (lowercase) that user has disabled
        """
        # Build a map of mwe_group_id -> expression for this sentence
        mwe_groups = {}
        for token in sentence_tokens:
            group_id = token.get("mwe_group_id")
            if group_id and group_id not in mwe_groups:
                # Find all tokens with this group_id and build the expression
                group_tokens = [t for t in sentence_tokens if t.get("mwe_group_id") == group_id]
                group_tokens.sort(key=lambda t: t.get("token_i", 0))
                expression = " ".join(t.get("text", "").strip() for t in group_tokens).lower()
                mwe_groups[group_id] = expression

        # Find which group_ids should be cleared
        groups_to_clear = set()
        for group_id, expression in mwe_groups.items():
            if expression in disabled_expressions:
                groups_to_clear.add(group_id)

        # Clear MWE metadata from tokens in disabled groups
        if groups_to_clear:
            for token in sentence_tokens:
                if token.get("mwe_group_id") in groups_to_clear:
                    token.pop("mwe_group_id", None)
                    token.pop("mwe_role", None)
                    token.pop("mwe_is_separated", None)
                    token.pop("mwe_partner_indices", None)

    @classmethod
    def user_article_summary_info(cls, user: User, article: Article, tokenization_cache=None):
        """
        Returns tokenized summary and title for an article with user bookmarks.

        Assumes cache is already populated via ArticleTokenizationCache.ensure_populated().
        Falls back to on-demand population if cache is missing (for backwards compatibility).

        Args:
            user: The user requesting the article summary
            article: The article to get summary info for
            tokenization_cache: Pre-fetched cache object (optional, avoids extra query)
        """
        import json
        from zeeguu.core.model.article_summary_context import ArticleSummaryContext
        from zeeguu.core.model.article_title_context import ArticleTitleContext
        from zeeguu.core.model.context_identifier import ContextIdentifier
        from zeeguu.core.model.context_type import ContextType
        from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
        from . import db

        result = {
            "id": article.id,
            "language": article.language.code,
        }

        # Use provided cache or fetch/create
        cache = tokenization_cache
        if not cache:
            cache = ArticleTokenizationCache.get_for_article(db.session, article.id)
        if not cache:
            cache, _ = ArticleTokenizationCache.ensure_populated(db.session, article)

        # Build summary response
        if article.summary and cache.tokenized_summary:
            try:
                tokenized_summary = json.loads(cache.tokenized_summary)
                summary_context_id = ContextIdentifier(
                    ContextType.ARTICLE_SUMMARY, article_id=article.id
                )
                result["tokenized_summary"] = {
                    "tokens": tokenized_summary,
                    "context_identifier": summary_context_id.as_dictionary(),
                    "past_bookmarks": ArticleSummaryContext.get_all_user_bookmarks_for_article_summary(
                        user.id, article.id
                    ),
                }
            except (json.JSONDecodeError, TypeError):
                log(f"[SUMMARY] Article {article.id} - Cache corrupt, skipping summary")

        # Build title response
        if cache.tokenized_title:
            try:
                tokenized_title = json.loads(cache.tokenized_title)
                title_context_id = ContextIdentifier(
                    ContextType.ARTICLE_TITLE, article_id=article.id
                )
                result["tokenized_title"] = {
                    "tokens": tokenized_title,
                    "context_identifier": title_context_id.as_dictionary(),
                    "past_bookmarks": ArticleTitleContext.get_all_user_bookmarks_for_article_title(
                        user.id, article.id
                    ),
                }
            except (json.JSONDecodeError, TypeError):
                log(f"[TITLE] Article {article.id} - Cache corrupt, skipping title")

        return result

    @classmethod
    def article_infos(cls, user, articles, select_appropriate=True):
        """
        Get article infos for a list of articles with proper cache handling.

        Uses batch optimization:
        1. Select appropriate versions and deduplicate
        2. Batch fetch existing caches (single query)
        3. Populate missing caches only
        4. Commit all cache writes
        5. Build response infos (pure reads)

        Args:
            user: The user requesting the articles
            articles: List of Article objects
            select_appropriate: If True, select appropriate version for user's CEFR level

        Returns:
            List of article info dicts, deduplicated by article ID
        """
        from zeeguu.core.model.article_tokenization_cache import ArticleTokenizationCache
        from . import db

        # Step 1: Select appropriate versions and deduplicate
        articles_to_process = []
        seen_ids = set()

        for article in articles:
            if select_appropriate:
                article = cls.select_appropriate_article_for_user(user, article)

            if article.id in seen_ids:
                continue
            seen_ids.add(article.id)
            articles_to_process.append(article)

        if not articles_to_process:
            return []

        # Step 2: Batch fetch existing caches (single query instead of N queries)
        article_ids = [a.id for a in articles_to_process]
        existing_caches = {
            c.article_id: c
            for c in db.session.query(ArticleTokenizationCache)
            .filter(ArticleTokenizationCache.article_id.in_(article_ids))
            .all()
        }

        # Step 3: Populate missing caches only
        for article in articles_to_process:
            if article.id not in existing_caches:
                cache, _ = ArticleTokenizationCache.ensure_populated(db.session, article)
                existing_caches[article.id] = cache

        # Step 4: Commit all cache writes
        db.session.commit()

        # Step 5: Build response infos (pure reads, using pre-fetched caches)
        return [
            cls.user_article_info(user, article, tokenization_cache=existing_caches.get(article.id))
            for article in articles_to_process
        ]
