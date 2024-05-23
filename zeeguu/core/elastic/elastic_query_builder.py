from elasticsearch_dsl import Search, Q, SF
from elasticsearch_dsl.query import MoreLikeThis
from datetime import timedelta, datetime
from zeeguu.core.model import Language


def match(key, value):
    return {"match": {key: value}}


def exists(field):
    return {"exists": {"field": field}}


def add_to_dict(dict, key, value):
    dict.update({key: value})


def array_of_lowercase_topics(topics):
    return [topic.lower() for topic in topics.split()]


def array_of_new_topics(topics):
    return topics.split(",")


def build_elastic_recommender_query(
    count,
    topics,
    unwanted_topics,
    user_topics,
    unwanted_user_topics,
    language,
    upper_bounds,
    lower_bounds,
    es_scale="30d",
    es_offset="1d",
    es_decay=0.5,
    es_weight=2.1,
    new_topics_to_include="",
    new_topics_to_exclude="",
    second_try=False,
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

    if user_topics:
        search_string = user_topics
        should.append(match("content", search_string))
        should.append(match("title", search_string))

    # Assumes if a user has new topics they won't be rolled
    # back to not have new topics again.
    # Essentially, if there are new topics the user won't be able
    # to access the old topics anymore.
    if new_topics_to_exclude != "":
        should_remove_topics = []
        topics_to_filter_out = array_of_new_topics(new_topics_to_exclude)
        for t in topics_to_filter_out:
            should_remove_topics.append({"match": {"new_topics": t}})
            should_remove_topics.append({"match": {"new_topics_inferred": t}})
        must_not.append({"bool": {"should": should_remove_topics}})
    else:
        unwanted_old_topics_arr = array_of_lowercase_topics(unwanted_topics)
        if len(unwanted_old_topics_arr) > 0:
            must_not.append({"terms": {"topics": unwanted_old_topics_arr}})

    if unwanted_user_topics:
        must_not.append(match("content", unwanted_user_topics))
        must_not.append(match("title", unwanted_user_topics))

    must.append(exists("published_time"))

    if new_topics_to_include != "":
        should_topics = []
        topics_to_find = array_of_new_topics(new_topics_to_include)
        for t in topics_to_find:
            should_topics.append({"match": {"new_topics": t}})
            should_topics.append({"match": {"new_topics_inferred": t}})
        must.append({"bool": {"should": should_topics}})
    else:
        topics_arr = array_of_lowercase_topics(topics)
        if len(topics_arr) > 0:
            must.append({"terms": {"topics": topics_arr}})

    if not second_try:
        # on the second try we do not add the range;
        # because we didn't find anything with it
        bool_query_body["query"]["bool"].update(
            {
                "filter": {
                    "range": {"fk_difficulty": {"gt": lower_bounds, "lt": upper_bounds}}
                }
            }
        )

    bool_query_body["query"]["bool"].update({"must": must})
    bool_query_body["query"]["bool"].update({"must_not": must_not})

    # Consider not showing articles without new topics?
    # bool_query_body["query"]["bool"].update(
    #     {
    #         "should": [
    #             {"exists": {"field": "new_topics"}},
    #             {"exists": {"field": "new_topics_inferred"}},
    #         ]
    #     }
    # )

    full_query = {"size": count, "query": {"function_score": {}}}

    function1 = {
        # original parameters by Simon & Marcus
        "gauss": {
            "published_time": {
                "scale": es_scale,
                "offset": es_offset,
                "decay": es_decay,
            }
        },
        "weight": es_weight,
        # "gauss": {"published_time": {"origin": "now", "scale": es_scale, "decay": es_decay}},
        # "weight": es_weight,
    }

    full_query["query"]["function_score"].update({"functions": [function1]})
    full_query["query"]["function_score"].update(bool_query_body)

    print(full_query)
    return full_query


def build_elastic_search_query(
    count,
    search_terms,
    topics,
    unwanted_topics,
    user_topics,
    unwanted_user_topics,
    language,
    upper_bounds,
    lower_bounds,
    es_scale="3d",
    es_offset="0d",
    es_decay=0.8,
    es_weight=4.2,
    new_topics_to_include="",
    new_topics_to_exclude="",
    second_try=False,
):
    """
    Builds an elastic search query for search terms.
    If called with second_try it drops the difficulty constraints
    It also weights more recent results higher

    """

    s = (
        Search()
        .query(
            Q("match", title=search_terms)
            | Q("match", content=search_terms)
            | Q("match", url=search_terms)
        )
        .filter("term", language=language.name.lower())
        .exclude("match", description="pg15")
    )

    if not second_try:
        s = s.filter("range", fk_difficulty={"gte": lower_bounds, "lte": upper_bounds})

    # using function scores to weight more recent results higher
    # https://github.com/elastic/elasticsearch-dsl-py/issues/608
    weighted_query = Q(
        "function_score",
        query=s.query,
        functions=[
            SF(
                "gauss",
                published_time={
                    "scale": es_scale,
                    "offset": es_offset,
                    "decay": es_decay,
                },
            )
        ],
    )

    query = {"size": count, "query": weighted_query.to_dict()}

    return query


def more_like_this_query(
    count,
    article_text,
    language,
    upper_bounds,
    lower_bounds,
    es_scale="3d",
    es_offset="1d",
    es_decay=0.8,
    es_weight=4.2,
    second_try=False,
):
    """
    Builds an elastic search query for search terms.
    If called with second_try it drops the difficulty constraints
    It also weights more recent results higher

    """

    s = (
        Search()
        .query(MoreLikeThis(like=article_text, fields=["title", "content"]))
        .filter("term", language=language.name.lower())
    )

    if not second_try:
        s = s.filter("range", fk_difficulty={"gte": lower_bounds, "lte": upper_bounds})

    # using function scores to weight more recent results higher
    # https://github.com/elastic/elasticsearch-dsl-py/issues/608
    weighted_query = Q(
        "function_score",
        query=s.query,
        functions=[
            SF(
                "gauss",
                published_time={
                    "scale": es_scale,
                    "offset": es_offset,
                    "decay": es_decay,
                },
            )
        ],
    )

    query = {"size": count, "query": weighted_query.to_dict()}

    return s.to_dict()


def build_elastic_semantic_sim_query(
    count,
    search_terms,
    topics,
    unwanted_topics,
    user_topics,
    unwanted_user_topics,
    language,
    upper_bounds,
    lower_bounds,
    article_sem_vec,
    article,
    es_scale="3d",
    es_decay=0.8,
    es_weight=4.2,
    second_try=False,
    n_candidates=100,
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
    if unwanted_topics is None:
        s = s.knn(
            field="sem_vec",
            k=count,
            num_candidates=n_candidates,
            query_vector=article_sem_vec,
            filter=(
                ~Q("ids", values=[article.id])
                & Q("match", **{"language.keyword": language.name})
            ),
        )
    else:
        s = s.knn(
            field="sem_vec",
            k=count,
            num_candidates=n_candidates,
            query_vector=article_sem_vec,
            filter=(
                ~Q("ids", values=[article.id])
                & (
                    Q("match", language__keyword=language.name)
                    & ~Q("match", **{"new_topics.keyword": ""})
                )
            ),
        )

    query = s.to_dict()
    print(query)
    return query


def build_elastic_semantic_sim_query_for_topic_cls(
    k_count,
    article,
    article_sem_vec,
    n_candidates=100,
):
    s = Search()
    s = s.knn(
        field="sem_vec",
        k=k_count,
        num_candidates=n_candidates,
        query_vector=article_sem_vec,
        filter=(
            ~Q("ids", values=[article.id])
            # & ~Q("match", **{"topic_keywords.keyword": ""})
            # & ~Q("match", **{"topics.keyword": ""})
            & Q("exists", field="new_topics")
            & ~Q("match", new_topics="")
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
                        "must": [{"match": {"language": language.name}}],
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
