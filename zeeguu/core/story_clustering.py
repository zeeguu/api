"""
Group articles that report the same story, so the feed shows one card per story.

Outlets run the same event within hours of each other (Le Figaro and HuffPost on
the Francis Renaud arrest, DR and Politiken on RJ Mitte's death), often from the
same wire copy, and a feed republishes an updated story under a new URL
(Politiken's "Dansk kvinde er/bliver 112 år"). The crawler's simhash check
catches none of these: it compares only within one feed and only near-verbatim
text.

At indexing time the article's full-text embedding (the `sem_vec` it is about to
be indexed with) is matched against articles of the same language published
in the STORY_WINDOW_HOURS before it. If the nearest one is at least
STORY_SIMILARITY_THRESHOLD similar, the article joins its story. The feed shows
one card per story (collapse_stories), and the card lists every outlet that ran
it equally (story_outlets), so the reader picks which version to open.

An outlet's own near-copy -- a story republished under a new URL, or the same
wire text in two of its feeds (one outlet can have several, e.g. Le Figaro and
Le Figaro - Actualité: outlet = domain) -- is at least REPUBLISH_SIMILARITY
and within REPUBLISH_WINDOW_HOURS (news runs on a daily cycle; a near-copy a
day later is the next day's take on a running story, not a republish):
the one with an image (then the newer) is kept, the other is marked broken as
DUPLICATE_IN_OUTLET and leaves the index. An outlet's follow-up on its own story
(Politiken's Motorregistret "lukket ned" -> "lukkede i over et døgn", 0.88)
joins the story but stays live.

Thresholds from tools/calibrate_story_clustering.py (fr + de, 3 days) and the
dry runs of tools/backfill_story_ids.py (fr + da), Oct 2026:
- every pair >= 0.90 was the same story; between 0.88 and 0.90 matches were
  follow-ups, merely related (Politiken's DSB "uge 42" -> "aflyser tog efter
  sporskiftefejl", 0.885) or real duplicates (Orélien, 0.893). Stories start
  at a round 0.90 rather than a value fitted to one week of data: missing a
  duplicate costs the learner a scroll; hiding a different story costs them
  content. Below 0.88, short wire items vs long features mix with same-topic
  pieces.
- identical wire copy scores 1.000; the closest same-outlet pair that was a
  distinct article scored 0.898, hence 0.95 for a republish.
Embedding title + summary instead was tried and separated worse.
"""

from datetime import timedelta

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.logging import log

STORY_SIMILARITY_THRESHOLD = 0.90
REPUBLISH_SIMILARITY = 0.95
# Hours, not the calendar day: an update at 00:30 republishes the 23:00 version
REPUBLISH_WINDOW_HOURS = 24
STORY_WINDOW_HOURS = 48


# A few neighbours, not one: the nearest may be a text a teacher uploaded
# (the index holds those too), which never joins a story; and an outlet's own
# copy may sit behind another outlet's copy of the same wire text.
NEIGHBOURS = 3


def _nearest_recent_articles(article, sem_vec):
    """[(article_id, cosine)] of the most similar earlier articles in the
    window, nearest first."""
    window = timedelta(hours=STORY_WINDOW_HOURS)
    s = Search().knn(
        field="sem_vec",
        k=NEIGHBOURS,
        num_candidates=100,
        query_vector=sem_vec,
        filter=(
            Q("exists", field="article_id")
            & ~Q("terms", article_id=[article.id])
            & Q("match", language__keyword=article.language.name)
            & Q(
                "range",
                published_time={
                    "gte": (article.published_time - window).isoformat(),
                    # Only earlier articles: a story's root is its earliest
                    # article, and a backfill in time order is consistent
                    "lte": article.published_time.isoformat(),
                },
            )
        ),
    )
    s = s.source(["article_id"])
    es = Elasticsearch(ES_CONN_STRING)
    hits = es.search(index=ES_ZINDEX, body=s.to_dict())["hits"]["hits"]
    # For a cosine dense_vector ES reports _score = (1 + cosine) / 2
    return [(h["_source"]["article_id"], 2 * h["_score"] - 1) for h in hits]


def same_story_neighbours(article, sem_vec):
    """[(neighbour, cosine)]: the nearest crawled articles at or above the
    story threshold, nearest first. Texts teachers uploaded are skipped."""
    from zeeguu.core.model import Article

    neighbours = []
    for neighbour_id, similarity in _nearest_recent_articles(article, sem_vec):
        if similarity < STORY_SIMILARITY_THRESHOLD:
            break  # nearest first: the rest are further still
        neighbour = Article.find_by_id(neighbour_id)
        if neighbour and neighbour.feed_id:
            neighbours.append((neighbour, similarity))
    return neighbours


def assign_story(article, sem_vec, session):
    """Join the story of the nearest recent article, if it is close enough;
    if it is the outlet's own near-copy, keep only one of the two.

    Only crawled articles form stories: a text a teacher uploaded has no feed,
    and must never be listed as an outlet on everyone's card.

    Never raises: a failure only means the article stays its own story.
    """
    if not sem_vec or not article.published_time or not article.feed_id:
        return
    try:
        neighbours = same_story_neighbours(article, sem_vec)
        if not neighbours:
            return
        nearest, similarity = neighbours[0]
        article.story_id = nearest.story_id or nearest.id
        session.add(article)
        session.commit()
        log(
            f"   Same story as article {nearest.id} "
            f"(similarity {similarity:.3f}) -> story {article.story_id}"
        )
        copies = [
            n
            for n, s in neighbours
            if _is_republish(article, n, s) and not n.broken
        ]
        if copies:
            _keep_one(article, copies, session)
    except Exception as e:
        session.rollback()
        log(f"   Story assignment failed for article {article.id}: {e}")


def _is_republish(article, earlier, similarity):
    """`article` is `earlier` again: same outlet, near-identical, same news day."""
    return (
        similarity >= REPUBLISH_SIMILARITY
        and earlier.url.domain_name_id == article.url.domain_name_id
        and article.published_time - earlier.published_time
        <= timedelta(hours=REPUBLISH_WINDOW_HOURS)
    )


def _live_story_members(story_ids):
    """The live crawled articles of these stories, with url + domain loaded."""
    from sqlalchemy.orm import joinedload
    from zeeguu.core.model import Article, Url

    return (
        Article.query.filter(
            (Article.id.in_(story_ids) & Article.story_id.is_(None))
            | Article.story_id.in_(story_ids),
            (Article.broken == 0) | Article.broken.is_(None),
            Article.feed_id.isnot(None),
        )
        .options(joinedload(Article.url).joinedload(Url.domain))
        .all()
    )


def _keep_one(article, copies, session):
    """The article and its outlet's near-copies are one text: keep the best."""
    from zeeguu.core.elastic.indexing import remove_from_index
    from zeeguu.core.model.article_broken_code_map import LowQualityTypes

    texts = [article] + copies
    kept = max(texts, key=_best_copy)
    for dropped in texts:
        if dropped is kept:
            continue
        dropped.set_as_broken(session, LowQualityTypes.DUPLICATE_IN_OUTLET)
        remove_from_index(dropped)
        log(
            f"   Article {dropped.id} marked broken: republish of {kept.id} "
            f"in {article.url.domain_name()}"
        )


def _story_key(content):
    # A story's first article has no story_id; the others point at its id.
    # Videos have their own id space, hence the type in the key.
    if not hasattr(content, "story_id"):
        return (type(content).__name__, content.id)
    return ("story", content.story_id or content.id)


def _newest(article):
    """Which member of a story gets the card (and stands for its outlet): the
    newest. The live members of a story are different texts -- other outlets,
    or an outlet's follow-ups -- and the latest carries the latest news, photo
    or not."""
    return article.published_time


def _best_copy(article):
    """Which copy of a republish is kept: the texts are the same, so the one
    with an image, then the newer (the updated one)."""
    has_image = getattr(article, "img_url_id", None) is not None
    return (has_image, article.published_time)


def collapse_stories(content):
    """Keep one item per story, in the position of the story's first item.

    Videos and articles without a story pass through untouched.
    """
    best = {}
    for c in content:
        key = _story_key(c)
        if key not in best or _newest(c) > _newest(best[key]):
            best[key] = c

    collapsed, placed = [], set()
    for c in content:
        key = _story_key(c)
        if key not in placed:
            placed.add(key)
            collapsed.append(best[key])
    return collapsed


def story_outlets(articles):
    """For each article whose story more than one outlet ran: one live article
    per outlet, the given one included, earliest first.

    Keyed by article id; single-outlet stories are left out.
    """
    keys = {a.story_id or a.id for a in articles if a.feed_id}
    if not keys:
        return {}
    by_story = {}
    for m in _live_story_members(keys):
        by_story.setdefault(m.story_id or m.id, []).append(m)

    outlets = {}
    for a in articles:
        per_outlet = {}
        for m in by_story.get(a.story_id or a.id, []):
            domain = m.url.domain_name_id
            # The card's own article stands for its outlet; another outlet
            # with several live articles (follow-ups) by its newest
            if domain == a.url.domain_name_id:
                if m.id == a.id:
                    per_outlet[domain] = m
            elif domain not in per_outlet or _newest(m) > _newest(per_outlet[domain]):
                per_outlet[domain] = m
        if len(per_outlet) > 1:
            outlets[a.id] = [
                {
                    "id": m.id,
                    "title": m.title,
                    "url": m.url.as_string(),
                    "domain": m.url.domain_name(),
                }
                for m in sorted(per_outlet.values(), key=lambda m: m.published_time)
            ]
    return outlets
