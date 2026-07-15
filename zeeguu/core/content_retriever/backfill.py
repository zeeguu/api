"""Promotion-on-join backfill (Task 5, phase 5).

When a reader opens up demand the last crawl didn't know about -- subscribes to a
topic, or picks a new learned language -- the demand-aware funnel will start
stocking that ``(language, topic)`` bucket, but only at the *next* crawl (up to
an hour away, more for low-frequency languages). The pilot-light floor keeps the
feed non-empty meanwhile, but a reader who just asked for a topic wants to see it
*now*.

Key insight: a dormant bucket is not empty of articles, only of *simplified*
ones. The crawler still downloads and stores the raw article; it just skips the
(expensive) simplification when the bucket has no demand. So the immediate
backfill doesn't need to crawl anything -- it simplifies a few of the raw
articles that are already sitting in the DB for this bucket. That's fast (LLM
only, no readability/download) and targeted.

Runs in a background thread (``run_in_background``) so it never blocks the
request; conservative caps keep it cheap.
"""

from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import aliased

import zeeguu.core
from zeeguu.logging import log


def _not_broken(article_cls):
    """Non-broken predicate: ``broken`` is 0 for healthy articles, but tolerate
    legacy NULLs too (the column is nullable)."""
    return or_(article_cls.broken == 0, article_cls.broken.is_(None))

# If the bucket already has at least this many freshly-simplified articles, the
# reader won't hit an empty feed and we skip the backfill entirely.
BACKFILL_FRESH_DAYS = 3
BACKFILL_MIN_FRESH = 3

# How far back to look for raw articles to simplify, and how many to add.
BACKFILL_LOOKBACK_DAYS = 7
BACKFILL_TARGET = 3


def fresh_simplified_count(session, language_id, topic_id, days=BACKFILL_FRESH_DAYS):
    """Count freshly-simplified articles available for a bucket.

    Simplified articles are the children (``parent_article_id`` set); topics live
    on the parent. ``topic_id=None`` counts across the whole language (used when a
    reader just picked a new learned language rather than a specific topic).
    """
    from zeeguu.core.model import Article, ArticleTopicMap

    cutoff = datetime.now() - timedelta(days=days)
    ParentArticle = aliased(Article)

    q = (
        session.query(Article.id)
        .join(ParentArticle, Article.parent_article_id == ParentArticle.id)
        .filter(ParentArticle.language_id == language_id)
        .filter(Article.published_time >= cutoff)
        .filter(_not_broken(Article))
    )
    if topic_id is not None:
        q = q.join(
            ArticleTopicMap, ArticleTopicMap.article_id == ParentArticle.id
        ).filter(ArticleTopicMap.topic_id == topic_id)
    return q.count()


def recent_unsimplified_articles(
    session, language_id, topic_id, days=BACKFILL_LOOKBACK_DAYS, limit=BACKFILL_TARGET
):
    """Recent raw (original, non-broken) articles for a bucket that have no
    simplified child yet -- the backfill's raw material, newest first."""
    from zeeguu.core.model import Article, ArticleTopicMap

    cutoff = datetime.now() - timedelta(days=days)
    Child = aliased(Article)

    q = (
        session.query(Article)
        .outerjoin(Child, Child.parent_article_id == Article.id)
        .filter(Article.parent_article_id.is_(None))  # originals only
        .filter(Child.id.is_(None))  # not yet simplified
        .filter(Article.language_id == language_id)
        .filter(Article.published_time >= cutoff)
        .filter(_not_broken(Article))
    )
    if topic_id is not None:
        q = q.join(
            ArticleTopicMap, ArticleTopicMap.article_id == Article.id
        ).filter(ArticleTopicMap.topic_id == topic_id)

    return q.order_by(Article.published_time.desc()).limit(limit).all()


def maybe_backfill_bucket(user_id, topic_id=None, provider="deepseek"):
    """Background entry point: give a just-joined reader's bucket a head start.

    Re-queries everything by id (runs in its own thread + app context). No-ops
    quietly if the bucket already has fresh inventory or there's nothing raw to
    simplify -- the next crawl and the pilot-light floor cover those cases.
    """
    from zeeguu.core.model import User
    from zeeguu.core.llm_services.simplification_and_classification import (
        simplify_and_classify,
    )

    session = zeeguu.core.model.db.session

    user = User.find_by_id(user_id)
    if not user or not user.learned_language:
        return
    language = user.learned_language

    fresh = fresh_simplified_count(session, language.id, topic_id)
    if fresh >= BACKFILL_MIN_FRESH:
        log(
            f"[backfill] {language.code}/topic={topic_id}: {fresh} fresh simplified "
            f"already available; skipping"
        )
        return

    candidates = recent_unsimplified_articles(session, language.id, topic_id)
    if not candidates:
        log(
            f"[backfill] {language.code}/topic={topic_id}: no raw articles to "
            f"simplify; next crawl + floor will cover it"
        )
        return

    simplified = 0
    for article in candidates:
        try:
            children, _classifications = simplify_and_classify(
                session, article, simplification_provider=provider
            )
            if children:
                simplified += 1
            session.commit()
        except Exception as e:
            session.rollback()
            log(f"[backfill] simplification failed for article {article.id}: {e}")

    log(
        f"[backfill] {language.code}/topic={topic_id}: simplified {simplified} "
        f"article(s) (had {fresh} fresh, targeted {BACKFILL_TARGET})"
    )
