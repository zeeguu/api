from elasticsearch_dsl import Search, Q, SF
from elasticsearch_dsl.query import MoreLikeThis
from datetime import timedelta, datetime
from zeeguu.core.model import Language

# pprint import removed for cleaner output
from zeeguu.core.model.article import Article


def match(key, value):
    return {"match": {key: value}}


def exists(field):
    return {"exists": {"field": field}}


def terms(key, values):
    return {"terms": {key: values}}


def add_to_dict(dict, key, value):
    dict.update({key: value})


def array_of_lowercase_topics(topics):
    return [topic.lower() for topic in topics.split()]


def array_of_topics(topics):
    return topics.split(",") if topics != "" else []


def more_like_this_query(count, article_text, language, page=0):
    """
    Builds an elastic search query for search terms.

    Uses the recency and the difficulty of articles to prioritize documents.
    """

    s = (
        Search()
        .query(MoreLikeThis(like=article_text, fields=["title", "content"]))
        .filter("term", language=language.name.lower())
    )

    return {"from": page * count, "size": count, "query": s.query.to_dict()}


CEFR_LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def get_cefr_levels_to_match(user_cefr_level):
    """
    Returns the list of CEFR levels that match the user's level.
    Includes exact match and compound levels where user is the upper half.
    E.g., A2 user matches: ["A2", "A1/A2"].

    NOTE: discovery (feed, topic browsing, search) no longer filters on CEFR at
    all — see build_elastic_recommender_query. What is left of this function
    serves tools/feed_delivery_health_check.py, which still probes per-level
    inventory as a canary on CEFR assessment coverage.
    """
    levels = [user_cefr_level]
    i = CEFR_LEVEL_ORDER.index(user_cefr_level)
    if i > 0:
        levels.append(f"{CEFR_LEVEL_ORDER[i - 1]}/{user_cefr_level}")
    return levels


def build_elastic_recommender_query(
    count,
    user_topics,
    unwanted_user_topics,
    language,
    es_scale,
    es_offset,
    es_decay,
    topics_to_include,
    topics_to_exclude,
    user_ignored_sources,
    articles_to_exclude=None,
    filter_disturbing=False,
    page=0,
):
    """
    Builds an elastic search query for article recommendations.

    Filters articles by:
    - Language
    - Topic preferences
    - Disturbing content (if enabled)

    Scores/ranks by recency (preferring recent articles).

    NOT filtered by CEFR level, deliberately. With on-demand simplification
    every article is readable at the learner's level — the feed card carries a
    level-appropriate summary (ArticleLevelSummary) and the body simplifies on
    request (POST /simplify_article/<id>) — so an article being "too hard" is no
    longer a reason to hide it. Filtering on available_cefr_levels used to mean
    the opposite: that field lists the levels for which a version was already
    generated, so once crawl-time simplification was retired it collapsed to the
    original's own level and a learner saw only articles a publisher happened to
    write at exactly their band (for Danish A2: ~3/day out of ~50). It also hid
    every article whose LLM assessment failed, which turned any assessment
    outage into an empty feed. Above-level readers are the mirror case and get
    the same treatment once we complexify.
    """

    # must = mandatory, has to occur
    # must not = has to not occur
    # should = nice to have (extra points if it matches)
    must = []

    must_not = []
    should = []

    bool_query_body = {"query": {"bool": {}}}  # initial empty bool query

    if language:
        must.append(match("language", language.name))

    if not user_topics:
        user_topics = ""

    topics_to_filter_out = array_of_topics(topics_to_exclude)
    if len(topics_to_exclude) > 0:
        should_remove_topics = []
        for t in topics_to_filter_out:
            should_remove_topics.append({"match": {"topics": t}})
            should_remove_topics.append({"match": {"topics_inferred": t}})
        must_not.append({"bool": {"should": should_remove_topics}})

    if unwanted_user_topics:
        must_not.append(match("content", unwanted_user_topics))
        must_not.append(match("title", unwanted_user_topics))

    # Exclude sources that user has repeatedly scrolled past (behavioral filtering)
    # Note: Each Article has a source_id that links to a Source record, which is an
    # abstraction for all content types (Article, Video, etc.). This filters based on
    # user behavior - sources they've scrolled past multiple times without engaging.
    if user_ignored_sources:
        must_not.append(
            terms(
                "source_id",
                user_ignored_sources,
            )
        )

    # Exclude specific article IDs (explicit filtering for saved/hidden articles)
    # Note: While there's potential overlap with user_ignored_sources above (since each
    # article has a source_id), these serve different purposes:
    # - user_ignored_sources: behavioral (what user scrolls past)
    # - articles_to_exclude: explicit user actions (saved or hidden articles)
    # An article might be excluded by both mechanisms, but that's fine - Elasticsearch
    # handles this efficiently, and the filters capture different user intentions.
    if articles_to_exclude:
        must_not.append(
            terms(
                "article_id",
                articles_to_exclude,
            )
        )

    # Filter disturbing content if user has enabled the preference
    if filter_disturbing:
        must_not.append({"match": {"is_disturbing": True}})

    must.append(exists("published_time"))
    # Allow both articles and videos in organic recommendations
    must.append({"bool": {"should": [exists("article_id"), exists("video_id")]}})

    topics_to_find = array_of_topics(topics_to_include)
    if len(topics_to_find) > 0:
        should_topics = []
        for t in topics_to_find:
            should_topics.append({"match": {"topics": t}})
            should_topics.append({"match": {"topics_inferred": t}})
        must.append({"bool": {"should": should_topics}})

    bool_query_body["query"]["bool"].update({"must": must})
    bool_query_body["query"]["bool"].update({"must_not": must_not})
    # bool_query_body["query"]["bool"].update({"should": should})

    full_query = {
        "from": page * count,
        "size": count,
        "query": {"function_score": {}},
    }

    recency_preference = {
        # original parameters by Simon & Marcus
        "exp": {
            "published_time": {
                "scale": es_scale,
                "offset": es_offset,
                "decay": es_decay,
            }
        },
    }

    # Note: difficulty scoring removed - we now filter by CEFR level instead
    full_query["query"]["function_score"].update({"functions": [recency_preference]})
    full_query["query"]["function_score"].update(bool_query_body)

    # Query logging removed for cleaner output
    return full_query


def build_elastic_search_query_for_videos(
    count,
    user_topics,
    unwanted_user_topics,
    language,
    topics_to_include,
    topics_to_exclude,
    user_ignored_sources,
    page,
):
    """
    Builds video search query. Similar to article recommender but with less
    emphasis on recency.

    No CEFR filter — same reasoning as build_elastic_recommender_query, and for
    videos the filter was worse than redundant: document_from_video never writes
    an available_cefr_levels field, so requiring a level in it excluded every
    video from every leveled user's results.
    """

    must = []
    must_not = []
    should = []

    bool_query_body = {"query": {"bool": {}}}  # initial empty bool query

    if language:
        must.append(match("language", language.name))

    if not user_topics:
        user_topics = ""

    topics_to_filter_out = array_of_topics(topics_to_exclude)
    if len(topics_to_exclude) > 0:
        should_remove_topics = []
        for t in topics_to_filter_out:
            should_remove_topics.append({"match": {"topics": t}})
            should_remove_topics.append({"match": {"topics_inferred": t}})
        must_not.append({"bool": {"should": should_remove_topics}})

    if unwanted_user_topics:
        must_not.append(match("content", unwanted_user_topics))
        must_not.append(match("title", unwanted_user_topics))

    if user_ignored_sources:
        must_not.append(
            terms(
                "source_id",
                user_ignored_sources,
            )
        )

    must.append(exists("published_time"))
    must.append(exists("video_id"))

    topics_to_find = array_of_topics(topics_to_include)
    if len(topics_to_find) > 0:
        should_topics = []
        for t in topics_to_find:
            should_topics.append({"match": {"topics": t}})
            should_topics.append({"match": {"topics_inferred": t}})
        must.append({"bool": {"should": should_topics}})

    bool_query_body["query"]["bool"].update({"must": must})
    bool_query_body["query"]["bool"].update({"must_not": must_not})

    full_query = {
        "from": page * count,
        "size": count,
        "query": {"function_score": {}},
    }

    recency_preference = {
        "exp": {
            "published_time": {
                "scale": "30d",
                "offset": "30d",
                "decay": 0.95,
            }
        },
    }

    # Note: difficulty scoring removed - we now filter by CEFR level instead
    full_query["query"]["function_score"].update({"functions": [recency_preference]})
    full_query["query"]["function_score"].update(bool_query_body)
    print("Video query...")
    return full_query


def build_elastic_search_query(
    count,
    search_terms,
    language,
    es_time_scale="1d",
    es_time_offset="1d",
    es_time_decay=0.65,
    page=0,
    use_published_priority=True,
):
    """
    Builds an elastic search query for search terms.

    Ranks by recency. No CEFR filter — a learner searching for a word wants the
    articles that contain it, and any of them can be simplified on demand (same
    reasoning as build_elastic_recommender_query).
    """

    s = (
        Search()
        .query(
            (
                Q("match", title={"query": search_terms, "operator": "and"})
                | Q("match", content={"query": search_terms, "operator": "and"})
            )
        )
        .filter("term", language=language.name.lower())
        .exclude("match", description="pg15")
    )

    # using function scores to weight more recent results higher
    # https://github.com/elastic/elasticsearch-dsl-py/issues/608
    preferences = []
    if use_published_priority:
        preferences.append(
            SF(
                "exp",
                published_time={
                    "scale": es_time_scale,
                    "offset": es_time_offset,
                    "decay": es_time_decay,
                },
            ),
        )
    # Note: difficulty scoring removed - we now filter by CEFR level instead
    weighted_query = Q("function_score", query=s.query, functions=preferences)

    query = {"from": page * count, "size": count, "query": weighted_query.to_dict()}
    print("## Search: ")
    return query


def build_elastic_semantic_sim_query_for_article(
    count,
    language,
    article_sem_vec,
    article,
    n_candidates=1000,
):
    """
    Builds an elastic search based on the KNN semantic embeddings, the filter can be a query object.
    https://elasticsearch-dsl.readthedocs.io/en/latest/search_dsl.html#k-nearest-neighbor-searches
    # Filter: Top k documents will have to fit this criteria. This is applied during the search.
    # Providing a Query means that the two are combined. These can take a boost to score how much it consideres of each.
    kNN search API finds a num_candidates number of approximate nearest neighbor candidates on each shard.
    The search computes the similarity of these candidate vectors to the query vector, selecting the k most
    similar results from each shard. The search then merges the results from each shard to return the global
    top k nearest neighbors.

    {'mappings': {'properties': {'author': {'fields': {'keyword': {'ignore_above': 256,
                                                               'type': 'keyword'}},
                                        'type': 'text'},
                             'content': {'fields': {'keyword': {'ignore_above': 256,
                                                                'type': 'keyword'}},
                                         'type': 'text'},
                             'fk_difficulty': {'type': 'long'},
                             'language': {'fields': {'keyword': {'ignore_above': 256,
                                                                 'type': 'keyword'}},
                                          'type': 'text'},
                             'published_time': {'type': 'date'},
                             'semantic_embedding': {'dims': 512,
                                                    'index': True,
                                                    'similarity': 'cosine',
                                                    'type': 'dense_vector'},
                             'summary': {'fields': {'keyword': {'ignore_above': 256,
                                                                'type': 'keyword'}},
                                         'type': 'text'},
                             'title': {'fields': {'keyword': {'ignore_above': 256,
                                                              'type': 'keyword'}},
                                       'type': 'text'},
                             'topics': {'fields': {'keyword': {'ignore_above': 256,
                                                               'type': 'keyword'}},
                                        'type': 'text'},
                             'url': {'fields': {'keyword': {'ignore_above': 256,
                                                            'type': 'keyword'}},
                                     'type': 'text'},
                             'video': {'type': 'long'},
                             'word_count': {'type': 'long'}}}}

    """
    s = Search()
    # s = s.exclude("match", id=article.id)

    s = s.knn(
        field="sem_vec",
        k=count,
        num_candidates=n_candidates,
        query_vector=article_sem_vec,
        filter=(
            ~Q("terms", **{"article_id": [article.id]})
            & (
                Q("match", language__keyword=language.name)
                & Q("exists", field="article_id")
                & ~Q("match", **{"topics.keyword": ""})
            )
        ),
    )

    query = s.to_dict()
    return query


def build_elastic_semantic_sim_query_for_text(
    count,
    text_embedding,
    n_candidates=1000,
    language=None,
):
    """
    Similar to build_elastic_semantic_sim_query, but taking a text embedding
    """
    s = Search()
    # s = s.exclude("match", id=article.id)
    if language:
        s = s.knn(
            field="sem_vec",
            k=count,
            num_candidates=n_candidates,
            query_vector=text_embedding,
            filter=(Q("match", language__keyword=language.name)),
        )
    else:
        s = s.knn(
            field="sem_vec",
            k=count,
            num_candidates=n_candidates,
            query_vector=text_embedding,
        )

    query = s.to_dict()
    return query


def build_elastic_semantic_sim_query_for_topic_cls(
    k_count,
    sem_vec,
    filter_ids: list[int] = None,
    n_candidates=3000,
):

    if filter_ids is None:
        filter_ids = []

    s = Search()
    s = s.knn(
        field="sem_vec",
        k=k_count,
        num_candidates=n_candidates,
        query_vector=sem_vec,
        filter=(
            Q("exists", field="article_id")
            & ~Q("terms", **{"article_id": filter_ids})
            # & ~Q("match", **{"url_keywords.keyword": ""})
            # & ~Q("match", **{"topics.keyword": ""})
            & Q(
                "exists", field="topics"
            )  # new_topics = topics that are not inferred, as opposed to new_topics_inferred
            & ~Q("match", topics="")
        ),
    )

    query = s.to_dict()

    # print(query)
    return query


def build_elastic_more_like_this_query(
    language: Language,
    like_documents: list[dict[str, str]],
    similar_to: list[str],
    cutoff_days: int,
    scale: str = "10d",
    offset: str = "4h",
    decay: float = 0.9,
):

    cutoff_date = datetime.now() - timedelta(days=cutoff_days)

    query = {
        "query": {
            "function_score": {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"language": language.name}},
                            {"exists": {"field": "article_id"}},
                        ],
                        "should": {
                            "more_like_this": {
                                "fields": similar_to,
                                "like": like_documents,
                                "min_term_freq": 2,
                                "max_query_terms": 25,
                                "min_doc_freq": 5,
                                "min_word_length": 3,
                            }
                        },
                        "filter": {
                            "bool": {
                                "must": [
                                    {
                                        "range": {
                                            "published_time": {
                                                "gte": cutoff_date.strftime(
                                                    "%Y-%m-%dT%H:%M:%S"
                                                ),
                                                "lte": "now",
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                    }
                },
                "functions": [
                    {
                        "gauss": {
                            "published_time": {
                                "origin": "now",
                                "scale": scale,
                                "offset": offset,
                                "decay": decay,
                            }
                        }
                    }
                ],
                "score_mode": "sum",
            }
        }
    }

    return query
