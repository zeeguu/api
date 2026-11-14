"""
The Evergreen tab: articles that don't go out of date, on the learner's
topics and keywords, a few new ones every day.

The crawler's LLM pass already labels every article `news` or `general`
(article.article_type). The home feed ignores the label and favors what is
recent, so the general ones sink within days. This recommender takes only
the general ones and ranks them without looking at the date.

Relevance:
1. matches one of the learner's keywords (search subscriptions)  +3
2. comes from a perennial feed (science, history: feed.retention_class)  +2
3. is in one of the learner's topics                              +1

"General" also catches soft features from news sites (an author's weekend,
a new film), which do date; the perennial-feed weight puts the real
explainers above them.

The daily list (no pill picked) is a slow conveyor, so a small pool lasts:
- on the first visit ever, the whole list is new;
- after that, up to NEW_PER_DAY never-shown articles a day go on top,
- and the rest are the most recently shown articles not yet opened, each for
  at most MAX_DAYS_SHOWN days; older ones wait at the back and return only
  when nothing else is left.
Within a day the list stays the same. Opened, hidden and reported articles
leave the tab. Ties are broken by a per-learner shuffle that does not change
between visits, so two learners with the same topics don't get the same list.

A picked pill (one topic or keyword) is browsing, not the daily list: it
shows that pill's articles, never-shown first, and records nothing.

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
from zeeguu.core.model.feed import Feed
from zeeguu.core.model.search import Search
from zeeguu.core.model.search_filter import SearchFilter
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.core.model.topic_filter import TopicFilter
from zeeguu.core.model.topic_subscription import TopicSubscription
from zeeguu.core.model.user_preference import UserPreference

KEYWORD_WEIGHT = 3
PERENNIAL_WEIGHT = 2
TOPIC_WEIGHT = 1

DEFAULT_COUNT = 10
NEW_PER_DAY = 3
MAX_DAYS_SHOWN = 4

# Caps on the candidate pool, so a language with many general articles still
# costs a bounded query.
MAX_PER_KEYWORD = 300
MAX_TOPIC_CANDIDATES = 2000


def _evergreen_articles(language):
    # Only what scoring reads: the pool can be a couple of thousand rows, and
    # content/htmlContent would make that tens of MB per page load. The chosen
    # few are fetched in full at the end.
    return Article.query.options(
        load_only(Article.id, Article.title, Article.summary, Article.feed_id),
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
    # Opening and hiding are recorded on the version the learner had in front
    # of them, which may be a simplified one. The tab lists originals, so
    # exclude the original of each such version too, or a text read at B1
    # stays on the tab as unread.
    opened_or_hidden = (
        db.session.query(UserArticle.article_id, Article.parent_article_id)
        .join(Article, Article.id == UserArticle.article_id)
        .filter(UserArticle.user_id == user.id)
        .filter(or_(UserArticle.opened.isnot(None), UserArticle.hidden.isnot(None)))
        .all()
    )
    reported = (
        db.session.query(UserArticleBrokenReport.article_id)
        .filter(UserArticleBrokenReport.user_id == user.id)
        .all()
    )
    excluded = {row[0] for row in reported}
    for article_id, parent_id in opened_or_hidden:
        excluded.add(article_id)
        if parent_id:
            excluded.add(parent_id)
    return excluded


def _mentions(article, keywords):
    text = f"{article.title or ''} {article.summary or ''}".lower()
    return any(k.lower() in text for k in keywords)


def _perennial_feed_ids(language):
    return {
        row[0]
        for row in db.session.query(Feed.id)
        .filter(Feed.language_id == language.id)
        .filter(Feed.retention_class == "perennial")
        .all()
    }


def evergreen_recommendations_for_user(
    user,
    language,
    count=DEFAULT_COUNT,
    now=None,
    only_topic_id=None,
    only_keyword=None,
):
    """Returns (articles, ids_new_today). Records the impressions of the daily
    list (not of a picked pill).

    only_topic_id / only_keyword: a pill picked in the tab's filter row; the
    list is then that topic's or that keyword's articles alone."""
    now = now or datetime.now()
    today = now.date()
    browsing_a_pill = bool(only_topic_id or only_keyword)

    keywords = _keywords(SearchSubscription, user, language)
    avoided = _keywords(SearchFilter, user, language)
    topic_ids = {s.topic_id for s in TopicSubscription.all_for_user(user)}
    avoided_topic_ids = {f.topic_id for f in TopicFilter.all_for_user(user)}

    if only_keyword:
        keywords, topic_ids = [only_keyword], set()
    elif only_topic_id:
        keywords, topic_ids = [], {only_topic_id}

    candidates = {}
    for keyword in keywords:
        for article in _keyword_matches(language, keyword):
            candidates[article.id] = article

    # Unfiltered, a learner without topics still gets the language's general
    # articles; filtered by a keyword, only that keyword's matches.
    if not only_keyword:
        topic_query = _evergreen_articles(language)
        if topic_ids:
            topic_query = topic_query.filter(
                Article.topics.any(ArticleTopicMap.topic_id.in_(topic_ids))
            )
        for article in topic_query.order_by(Article.id.desc()).limit(
            MAX_TOPIC_CANDIDATES
        ):
            candidates.setdefault(article.id, article)

    excluded = _excluded_article_ids(user)
    # the same safety setting the home feed honors (a teacher or a parent may
    # have set it)
    if UserPreference.is_filter_disturbing_content_enabled(user):
        excluded |= _disturbing_ids(list(candidates))
    impressions = EvergreenImpression.for_user(user.id)
    perennial_feeds = _perennial_feed_ids(language)

    def relevance(article):
        s = 0
        if keywords and _mentions(article, keywords):
            s += KEYWORD_WEIGHT
        if article.feed_id in perennial_feeds:
            s += PERENNIAL_WEIGHT
        if {t.topic_id for t in article.topics} & topic_ids:
            s += TOPIC_WEIGHT
        return s

    def by_relevance(article):
        # hash of an int tuple is stable across processes: the same shuffle
        # on every visit, a different one per learner
        return (-relevance(article), hash((user.id, article.id)))

    eligible = []
    for article in candidates.values():
        if article.id in excluded:
            continue
        if avoided and _mentions(article, avoided):
            continue
        if avoided_topic_ids and {t.topic_id for t in article.topics} & avoided_topic_ids:
            continue
        eligible.append(article)

    def is_new_today(article):
        seen = impressions.get(article.id)
        return seen is None or seen.first_shown.date() == today

    if browsing_a_pill:
        chosen = sorted(eligible, key=lambda a: (not is_new_today(a), by_relevance(a)))[
            :count
        ]
    else:
        chosen = _daily_list(eligible, impressions, today, count, by_relevance)

    chosen_ids = [a.id for a in chosen]
    new_today = {a.id for a in chosen if is_new_today(a)}
    if not browsing_a_pill:
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


def _daily_list(eligible, impressions, today, count, by_relevance):
    """Up to NEW_PER_DAY never-shown articles on top (the whole list on the
    first visit ever), then the most recently shown unopened ones, each for at
    most MAX_DAYS_SHOWN days. Whatever is short is filled with more new ones,
    then with the ones waiting at the back."""
    first_today, never_shown, carried, waiting = [], [], [], []
    for article in eligible:
        seen = impressions.get(article.id)
        if seen is None:
            never_shown.append(article)
        elif seen.first_shown.date() == today:
            first_today.append(article)
        elif seen.last_shown.date() == today or seen.times_shown < MAX_DAYS_SHOWN:
            carried.append(article)
        else:
            waiting.append(article)

    first_today.sort(key=by_relevance)
    never_shown.sort(key=by_relevance)
    # shown today first (the list holds still within a day), then the most
    # recently introduced
    carried.sort(
        key=lambda a: (
            impressions[a.id].last_shown.date() != today,
            -impressions[a.id].first_shown.timestamp(),
            by_relevance(a),
        )
    )
    waiting.sort(key=lambda a: (impressions[a.id].times_shown, by_relevance(a)))

    new_quota = count if not impressions else NEW_PER_DAY
    new_slots = max(0, new_quota - len(first_today))
    chosen = first_today + never_shown[:new_slots] + carried
    if len(chosen) < count:
        chosen += never_shown[new_slots:]
    if len(chosen) < count:
        chosen += waiting
    return chosen[:count]
