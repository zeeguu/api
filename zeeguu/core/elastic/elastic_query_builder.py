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


def build_elastic_recommender_query(
    count,
    user_topics,
    unwanted_user_topics,
    language,
    upper_bounds,
    lower_bounds,
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

    Builds an elastic search query.
    Does this by building a big JSON object.

    Example of a final query body:
    {'size': 20.0, 'query':
        {'bool':
            {
            'filter':
                {
                'range':
                    {
                    'fk_difficulty':
                        {
                        'gt': 0,
                         'lt': 100
                         }
                    }
                },
            'must': [
                {'match': {'language': 'English'}}
            ],
            'must_not': [
                {'match': {'topics': 'Health'}},
                {'match': {'content': 'messi'}},
                {'match': {'title': 'messi'}}
                ]
            }
        }
    }

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
        # I am unsure if we should keep he weight for this one.
        # Right now, I guess it means we weigh both the difficulty
        # and recency equaly which I think it's the behaviour we would ike.
        # "weight": es_weight,
        # "gauss": {"published_time": {"origin": "now", "scale": es_scale, "decay": es_decay}},
    }

    difficulty_prefference = {
        "exp": {
            "fk_difficulty": {
                "origin": ((upper_bounds + lower_bounds) / 2),
                "scale": 21,
            }
        },
    }

    full_query["query"]["function_score"].update(
        {"functions": [recency_preference, difficulty_prefference]}
    )
    full_query["query"]["function_score"].update(bool_query_body)

    # Query logging removed for cleaner output
    return full_query


def build_elastic_search_query_for_videos(
    count,
    user_topics,
    unwanted_user_topics,
    language,
    upper_bounds,
    lower_bounds,
    topics_to_include,
    topics_to_exclude,
    user_ignored_sources,
    page,
):
    """
    At the moment this query is very similar to the articles query 'build_elastic_recommender_query'
    The difference here is that we don't enforce the recency as much as in the articles.

    We expect videos to come at a much lower pace when compared to the articles.
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
    # bool_query_body["query"]["bool"].update({"should": should})

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
        # I am unsure if we should keep he weight for this one.
        # Right now, I guess it means we weigh both the difficulty
        # and recency equaly which I think it's the behaviour we would ike.
        # "weight": es_weight,
        # "gauss": {"published_time": {"origin": "now", "scale": es_scale, "decay": es_decay}},
    }

    difficulty_prefference = {
        "exp": {
            "fk_difficulty": {
                "origin": ((upper_bounds + lower_bounds) / 2),
                "scale": 21,
            }
        },
    }

    full_query["query"]["function_score"].update(
        {"functions": [recency_preference, difficulty_prefference]}
    )
    full_query["query"]["function_score"].update(bool_query_body)
    print("Video query...")
    # Query logging removed for cleaner output
    return full_query


def build_elastic_search_query(
    count,
    search_terms,
    language,
    upper_bounds,
    lower_bounds,
    es_time_scale="1d",
    es_time_offset="1d",
    es_time_decay=0.65,
    page=0,
    use_published_priority=True,
    use_readability_priority=True,
):
    """
    Builds an elastic search query for search terms.

    Uses the recency and the difficulty of articles to prioritize documents.
    """

    s = (
        Search()
        .query((Q("match", title=search_terms) | Q("match", content=search_terms)))
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
    if use_readability_priority:
        preferences.append(
            SF(
                "exp",
                fk_difficulty={
                    "origin": ((upper_bounds + lower_bounds) / 2),
                    "scale": 21,
                    "decay": 0.5,
                },
            ),
        )
    weighted_query = Q("function_score", query=s.query, functions=preferences)

    query = {"from": page * count, "size": count, "query": weighted_query.to_dict()}
    print("## Search: ")
    # Query logging removed for cleaner output
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
