from elasticsearch_dsl import Search, Q, SF
from datetime import timedelta, datetime
from zeeguu.core.model import Language
from pprint import pprint


def match(key, value):
    return {"match": {key: value}}


def exists(field):
    return {"exists": {"field": field}}


def add_to_dict(dict, key, value):
    dict.update({key: value})


def array_of_lowercase_topics(topics):
    return [topic.lower() for topic in topics.split()]


def build_elastic_recommender_query(
    count,
    topics,
    unwanted_topics,
    user_topics,
    unwanted_user_topics,
    language,
    upper_bounds,
    lower_bounds,
    es_scale,
    es_offset,
    es_decay,
    es_weight,
    page,
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

    # if user_topics:
    #     search_string = user_topics
    #     should.append(match("content", search_string))
    #     should.append(match("title", search_string))

    unwanted_topics_arr = array_of_lowercase_topics(unwanted_topics)
    if len(unwanted_topics_arr) > 0:
        must_not.append({"terms": {"topics": unwanted_topics_arr}})

    if unwanted_user_topics:
        must_not.append(match("content", unwanted_user_topics))
        must_not.append(match("title", unwanted_user_topics))

    must.append(exists("published_time"))
    topics_arr = array_of_lowercase_topics(topics)
    if len(topics_arr) > 0:
        must.append({"terms": {"topics": topics_arr}})

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
    pprint(full_query)
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
        .query(Q("match", title=search_terms) | Q("match", content=search_terms))
        .filter("term", language=language.name.lower())
        .exclude("match", description="pg15")
    )
    # using function scores to weight more recent results higher
    # https://github.com/elastic/elasticsearch-dsl-py/issues/608
    preferences = []
    print("Current values: ", use_published_priority, use_readability_priority)
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
    print("Performing Search: ")
    pprint(query)
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
