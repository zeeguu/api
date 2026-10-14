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
STORY_SIMILARITY_THRESHOLD similar, the article joins its story.

Two articles of one story from the same outlet (same domain: one outlet can
have several feeds, e.g. Le Figaro and Le Figaro - Actualité) are a republish,
not a second voice: the one with an image (then the newer) is kept, the other
is marked broken as DUPLICATE_IN_OUTLET and leaves the index. Across outlets
all are kept: the feed shows one card per story (collapse_stories) and the card
lists every outlet equally (story_outlets), so the reader picks which to open.

The threshold comes from tools/calibrate_story_clustering.py over three days of
French and German (Oct 2026): at >= 0.88 every pair was the same story; between
0.80 and 0.88 real duplicates (a short wire item vs a long feature) mix with
follow-ups and same-topic pieces. Missing a duplicate costs the learner a
scroll; hiding a different story costs them content, so the threshold errs high.
Embedding title + summary instead was tried and separated worse.
"""

from datetime import timedelta

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.logging import log

STORY_SIMILARITY_THRESHOLD = 0.88
STORY_WINDOW_HOURS = 48


def _nearest_recent_article(article, sem_vec):
    """(article_id, cosine) of the most similar earlier article in the window, or None."""
    window = timedelta(hours=STORY_WINDOW_HOURS)
    s = Search().knn(
        field="sem_vec",
        k=1,
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
    if not hits:
        return None
    # For a cosine dense_vector ES reports _score = (1 + cosine) / 2
    return hits[0]["_source"]["article_id"], 2 * hits[0]["_score"] - 1


def assign_story(article, sem_vec, session):
    """Join the story of the nearest recent article, if it is close enough.

    Never raises: a failure only means the article stays its own story.
    """
    from zeeguu.core.model import Article

    if not sem_vec or not article.published_time:
        return
    try:
        nearest = _nearest_recent_article(article, sem_vec)
        if not nearest:
            return
        neighbour_id, similarity = nearest
        if similarity < STORY_SIMILARITY_THRESHOLD:
            return
        neighbour = Article.find_by_id(neighbour_id)
        if not neighbour:
            return
        article.story_id = neighbour.story_id or neighbour.id
        session.add(article)
        session.commit()
        log(
            f"   Same story as article {neighbour.id} "
            f"(similarity {similarity:.3f}) -> story {article.story_id}"
        )
        if _same_outlet(neighbour, article):
            _keep_one_per_outlet(article, neighbour, session)
    except Exception as e:
        session.rollback()
        log(f"   Story assignment failed for article {article.id}: {e}")


def _same_outlet(a, b):
    return a.url.domain_name_id == b.url.domain_name_id


def _keep_one_per_outlet(article, neighbour, session):
    from zeeguu.core.elastic.indexing import remove_from_index
    from zeeguu.core.model.article_broken_code_map import LowQualityTypes

    dropped = min(article, neighbour, key=_preference)
    dropped.set_as_broken(session, LowQualityTypes.DUPLICATE_IN_OUTLET)
    remove_from_index(dropped)
    log(f"   Article {dropped.id} marked broken: duplicate in {article.url.domain_name()}")


def _story_key(content):
    # A story's first article has no story_id; the others point at its id.
    # Videos have their own id space, hence the type in the key.
    if not hasattr(content, "story_id"):
        return (type(content).__name__, content.id)
    return ("story", content.story_id or content.id)


def _preference(article):
    """Which member of a story gets the card: one with an image, then the newest
    (a republished story is the updated one)."""
    has_image = getattr(article, "img_url_id", None) is not None
    return (has_image, article.published_time)


def collapse_stories(content):
    """Keep one item per story, in the position of the story's first item.

    Videos and articles without a story pass through untouched.
    """
    best = {}
    for c in content:
        key = _story_key(c)
        if key not in best or _preference(c) > _preference(best[key]):
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
    from zeeguu.core.model import Article

    keys = {a.story_id or a.id for a in articles}
    if not keys:
        return {}
    members = Article.query.filter(
        (Article.id.in_(keys) & Article.story_id.is_(None))
        | Article.story_id.in_(keys),
        (Article.broken == 0) | Article.broken.is_(None),
    ).all()
    by_story = {}
    for m in members:
        by_story.setdefault(m.story_id or m.id, []).append(m)

    outlets = {}
    for a in articles:
        per_outlet = {}
        for m in by_story.get(a.story_id or a.id, []):
            domain = m.url.domain_name_id
            # The card's own article stands for its outlet
            if m.id == a.id or (
                domain not in per_outlet and domain != a.url.domain_name_id
            ):
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
