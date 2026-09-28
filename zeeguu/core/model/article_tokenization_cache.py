import json
import logging

from sqlalchemy import Column, Integer, UnicodeText, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError, OperationalError
from datetime import datetime, timedelta
from zeeguu.core.model.db import db

log = logging.getLogger(__name__)


class ArticleTokenizationCache(db.Model):
    """
    Caches tokenized content, summary and title for articles to avoid expensive
    CPU-bound Stanza tokenization and MWE detection on every request.

    1-to-1 relationship with Article - keeps article table lean while providing
    fast lookups for cached tokenization.
    """
    __tablename__ = "article_tokenization_cache"

    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), primary_key=True)
    tokenized_content = Column(UnicodeText)  # Full article content with MWE detection
    # TODO: tokenized_summary and tokenized_title are now redundant since tokenized_content
    # includes everything. Consider removing these columns in a future cleanup.
    tokenized_summary = Column(UnicodeText)
    tokenized_title = Column(UnicodeText)
    created_at = Column(DateTime, default=datetime.now)

    article = relationship("Article", back_populates="tokenization_cache")

    @classmethod
    def find_or_create(cls, session, article):
        """
        Find existing cache or create new empty cache for article.

        Flushes immediately to avoid deadlocks from autoflush during
        subsequent queries in the same request. Handles race conditions
        where multiple concurrent requests try to create the same cache.
        """
        cache = session.query(cls).filter_by(article_id=article.id).first()
        if cache:
            return cache

        # Try to create and flush immediately
        cache = cls(article_id=article.id)
        session.add(cache)
        try:
            session.flush()
        except IntegrityError:
            # Another request created it first - rollback and fetch
            session.rollback()
            cache = session.query(cls).filter_by(article_id=article.id).first()
        except OperationalError as e:
            # Lock wait timeout or other DB operational error - rollback to clean session state
            # This prevents PendingRollbackError in subsequent operations
            log.warning(f"[CACHE] OperationalError during cache creation for article {article.id}: {e}")
            session.rollback()
            # Try to fetch existing cache (another process may have created it)
            cache = session.query(cls).filter_by(article_id=article.id).first()

        return cache

    @classmethod
    def get_for_article(cls, session, article_id):
        """Get cache for article, returns None if not found"""
        return session.query(cls).filter_by(article_id=article_id).first()

    @classmethod
    def ensure_populated(cls, session, article):
        """
        Ensure cache exists and is populated with tokenized summary and title.

        This separates the write concern (populating cache) from the read concern
        (using cached data), allowing callers to batch all writes before reads.
        """
        from zeeguu.core.mwe import tokenize_for_reading

        cache = cls.find_or_create(session, article)
        modified = False

        # Populate summary if needed
        if article.summary and not cache.tokenized_summary:
            tokenized = tokenize_for_reading(article.summary, article.language, mode="stanza")
            cache.tokenized_summary = json.dumps(tokenized)
            modified = True
            log.info(f"[CACHE] Article {article.id} - Tokenized and cached summary with MWE")

        # Populate title if needed
        if not cache.tokenized_title:
            tokenized = tokenize_for_reading(article.title, article.language, mode="stanza")
            cache.tokenized_title = json.dumps(tokenized)
            modified = True
            log.info(f"[CACHE] Article {article.id} - Tokenized and cached title with MWE")

        return cache, modified

    @classmethod
    def ensure_populated_batch(cls, session, articles):
        """
        Populate caches for many articles with one stanza call per language.

        ensure_populated() sends one HTTP request per text, so warming N
        articles costs 2N serial round trips against a single-threaded service.
        The service already exposes /tokenize_batch (and the client wraps it);
        this groups by language and uses it, because MWE enrichment afterwards
        is local and cheap -- the round trips were the whole cost.

        Returns (populated, failed). Caller commits.
        """
        from collections import defaultdict
        from zeeguu.core.mwe import enrich_tokens_with_mwe
        from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

        # (article, field, text) for everything still missing
        jobs_by_language = defaultdict(list)
        for article in articles:
            cache = cls.find_or_create(session, article)
            if article.summary and not cache.tokenized_summary:
                jobs_by_language[article.language].append((cache, "tokenized_summary", article.summary))
            if article.title and not cache.tokenized_title:
                jobs_by_language[article.language].append((cache, "tokenized_title", article.title))

        populated = 0
        failed = 0
        for language, jobs in jobs_by_language.items():
            tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
            if not hasattr(tokenizer, "tokenize_batch"):
                # Local stanza tokenizer: no batch endpoint, one at a time.
                results = [tokenizer.tokenize_text(t, flatten=False) for _, _, t in jobs]
            else:
                results = tokenizer.tokenize_batch([t for _, _, t in jobs], flatten=False)

            for (cache, field, _), tokens in zip(jobs, results):
                try:
                    enriched = enrich_tokens_with_mwe(tokens, language.code, mode="stanza")
                    setattr(cache, field, json.dumps(enriched))
                    populated += 1
                except Exception as e:
                    failed += 1
                    log.warning(f"[CACHE] {field} failed for article {cache.article_id}: {e}")

        return populated, failed

    @classmethod
    def cheap_tokens(cls, text, language):
        """
        Tokenize with NLTK, locally and immediately, for a read path that must
        not block.

        Same paragraphs->sentences->tokens shape the stanza path produces, so
        the client renders and taps words exactly as usual. What is missing is
        MWE grouping: expressions come out as separate words until the real
        cache lands. That is a visible downgrade, and a deliberate one --
        the alternative on a cache miss was an inline call to the stanza
        service, which is one single-threaded worker for the whole install and
        has been logging 5-8s for titles of a few dozen characters.

        Never persisted: writing these into the cache would make the miss
        permanent and silently cost every reader their expressions.
        """
        from zeeguu.core.tokenization import get_tokenizer
        from zeeguu.core.tokenization.zeeguu_tokenizer import TokenizerModel

        if not text:
            return None
        tokenizer = get_tokenizer(language, TokenizerModel.NLTK)
        return tokenizer.tokenize_text(text, flatten=False)

    @classmethod
    def delete_for_article(cls, session, article_id):
        """Delete cache for a specific article. Returns True if deleted."""
        deleted = session.query(cls).filter_by(article_id=article_id).delete()
        session.commit()
        log.info(f"[CACHE] Deleted cache for article {article_id}")
        return deleted > 0

    @classmethod
    def count_for_language(cls, session, language_code):
        """How many cache entries belong to articles in `language_code`."""
        return cls._query_for_language(session, language_code).count()

    @classmethod
    def delete_for_language(cls, session, language_code):
        """Drop every cache entry for one language. Returns rows deleted.

        Needed when tokenization itself changes -- a new MWE lexicon entry, a
        parser upgrade -- because nothing else invalidates these rows. There is
        no version column, so an article tokenized before the change keeps its
        old grouping until the 7-day sweep reaches it, which is far too long to
        wait to see a fix. Entries are re-created on demand on next read.
        """
        # As a subquery, not a list of ids: a language with a large archive
        # would otherwise be pulled into Python and sent back as one enormous
        # IN clause.
        deleted = (
            session.query(cls)
            .filter(cls.article_id.in_(cls._article_ids_for_language(session, language_code)))
            .delete(synchronize_session=False)
        )
        session.commit()
        log.info(f"[CACHE] Deleted {deleted} cache entries for language {language_code}")
        return deleted

    @classmethod
    def _article_ids_for_language(cls, session, language_code):
        """Sub-selectable query over article ids in `language_code`."""
        # Imported here rather than at module scope: article imports this
        # module back for the tokenization_cache relationship.
        from zeeguu.core.model.article import Article
        from zeeguu.core.model.language import Language

        return (
            session.query(Article.id)
            .join(Language, Language.id == Article.language_id)
            .filter(Language.code == language_code)
            .scalar_subquery()
        )

    @classmethod
    def _query_for_language(cls, session, language_code):
        """Cache rows whose article is in `language_code`."""
        return session.query(cls.article_id).filter(
            cls.article_id.in_(cls._article_ids_for_language(session, language_code))
        )

    @classmethod
    def delete_older_than(cls, session, days=7):
        """Delete cache entries older than N days. Returns count of deleted rows."""
        cutoff = datetime.now() - timedelta(days=days)
        deleted = session.query(cls).filter(cls.created_at < cutoff).delete()
        session.commit()
        log.info(f"[CACHE-CLEANUP] Deleted {deleted} cache entries older than {days} days")
        return deleted
