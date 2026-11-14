"""
The Evergreen tab: articles that don't go out of date, on the learner's
topics and keywords, with something new on every visit.

The crawler's LLM pass already labels every article `news` or `general`
(article.article_type). The home feed ignores the label and favors what is
recent, so the general ones sink within days. This recommender takes only
the general ones and ranks them without looking at the date:

1. matches one of the learner's keywords (search subscriptions)  +3
2. is in one of the learner's topics                              +1
3. never shown on the tab before, or first shown today            +2
4. shown on an earlier day and not opened                         -1 per day shown

Opened articles leave the tab: they are in the learner's history. Within a
day the list stays the same (today's new ones keep their bonus), and the next
day the ones passed by drop behind ones never seen. Ties are broken by a
per-learner shuffle that does not change between visits, so two learners
with the same topics don't get the same list.

Runs on the database alone, not Elasticsearch: one language has a few
thousand general articles, and the candidate pool is capped.
"""

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import load_only, selectinload

from zeeguu.core.model import Article, UserArticle, UserArticleBrokenReport
from zeeguu.core.model.article_classification import ArticleClassification
from zeeguu.core.model.article_topic_map import ArticleTopicMap
from zeeguu.core.model.db import db
from zeeguu.core.model.evergreen_impression import EvergreenImpression
from zeeguu.core.model.search import Search
from zeeguu.core.model.search_filter import SearchFilter
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.core.model.topic_filter import TopicFilter
from zeeguu.core.model.topic_subscription import TopicSubscription
from zeeguu.core.model.user_preference import UserPreference

KEYWORD_WEIGHT = 3
TOPIC_WEIGHT = 1
UNSEEN_BONUS = 2

# Caps on the candidate pool, so a language with many general articles still
# costs a bounded query.
MAX_PER_KEYWORD = 300
MAX_TOPIC_CANDIDATES = 2000


def _evergreen_articles(language):
    # Only what scoring reads: the pool can be a couple of thousand rows, and
    # content/htmlContent would make that tens of MB per page load. The chosen
    # few are fetched in full at the end.
    return Article.query.options(
        load_only(Article.id, Article.title, Article.summary),
        selectinload(Article.topics),
    ).filter(
        Article.language_id == language.id,
        Article.article_type == "general",
        Article.parent_article_id.is_(None),
        Article.uploader_id.is_(None),
        or_(Article.broken.is_(None), Article.broken == 0),
        or_(Article.deleted.is_(None), Article.deleted == 0),
        or_(Article.video.is_(None), Article.video == 0),
    )


def _keyword_matches(language, keyword):
    pattern = f"%{keyword}%"
    return (
        _evergreen_articles(language)
        .filter(or_(Article.title.ilike(pattern), Article.summary.ilike(pattern)))
        .order_by(Article.id.desc())
        .limit(MAX_PER_KEYWORD)
        .all()
    )


def _keywords(model, user, language):
    return [
        each.search.keywords
        for each in model.query.join(Search)
        .filter(model.user == user)
        .filter(Search.language_id == language.id)
        .all()
    ]


def _disturbing_ids(article_ids):
    if not article_ids:
        return set()
    rows = (
        db.session.query(ArticleClassification.article_id)
        .filter(ArticleClassification.article_id.in_(article_ids))
        .filter(ArticleClassification.classification_type == "DISTURBING")
        .all()
    )
    return {row[0] for row in rows}


def _excluded_article_ids(user):
    opened_or_hidden = (
        db.session.query(UserArticle.article_id)
        .filter(UserArticle.user_id == user.id)
        .filter(or_(UserArticle.opened.isnot(None), UserArticle.hidden.isnot(None)))
        .all()
    )
    reported = (
        db.session.query(UserArticleBrokenReport.article_id)
        .filter(UserArticleBrokenReport.user_id == user.id)
        .all()
    )
    return {row[0] for row in opened_or_hidden + reported}


def _mentions(article, keywords):
    text = f"{article.title or ''} {article.summary or ''}".lower()
    return any(k.lower() in text for k in keywords)


def evergreen_recommendations_for_user(user, language, count=12, now=None):
    """Returns (articles, ids_new_today). Records the impressions."""
    now = now or datetime.now()

    keywords = _keywords(SearchSubscription, user, language)
    avoided = _keywords(SearchFilter, user, language)
    topic_ids = {s.topic_id for s in TopicSubscription.all_for_user(user)}
    avoided_topic_ids = {f.topic_id for f in TopicFilter.all_for_user(user)}

    candidates = {}
    for keyword in keywords:
        for article in _keyword_matches(language, keyword):
            candidates[article.id] = article

    topic_query = _evergreen_articles(language)
    if topic_ids:
        topic_query = topic_query.filter(
            Article.topics.any(ArticleTopicMap.topic_id.in_(topic_ids))
        )
    for article in topic_query.order_by(Article.id.desc()).limit(MAX_TOPIC_CANDIDATES):
        candidates.setdefault(article.id, article)

    excluded = _excluded_article_ids(user)
    # the same safety setting the home feed honors (a teacher or a parent may
    # have set it)
    if UserPreference.is_filter_disturbing_content_enabled(user):
        excluded |= _disturbing_ids(list(candidates))
    impressions = EvergreenImpression.for_user(user.id)

    def score(article):
        article_topics = {t.topic_id for t in article.topics}
        s = 0
        if keywords and _mentions(article, keywords):
            s += KEYWORD_WEIGHT
        if article_topics & topic_ids:
            s += TOPIC_WEIGHT
        seen = impressions.get(article.id)
        if seen is None or seen.first_shown.date() == now.date():
            s += UNSEEN_BONUS
        else:
            s -= seen.times_shown
        return s

    ranked = []
    for article in candidates.values():
        if article.id in excluded:
            continue
        if avoided and _mentions(article, avoided):
            continue
        if avoided_topic_ids and {t.topic_id for t in article.topics} & avoided_topic_ids:
            continue
        # hash of an int tuple is stable across processes: the same shuffle
        # on every visit, a different one per learner
        ranked.append((-score(article), hash((user.id, article.id)), article))

    ranked.sort(key=lambda r: (r[0], r[1]))
    chosen_ids = [r[2].id for r in ranked[:count]]

    new_today = {
        i
        for i in chosen_ids
        if i not in impressions or impressions[i].first_shown.date() == now.date()
    }
    EvergreenImpression.record(
        db.session, user.id, chosen_ids, known=impressions, when=now
    )

    # The pool was loaded with only the columns scoring needs; the article
    # infos need the whole row.
    full = {
        a.id: a
        for a in Article.query.populate_existing()
        .filter(Article.id.in_(chosen_ids))
        .all()
    }
    return [full[i] for i in chosen_ids if i in full], new_today
