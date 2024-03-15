from elasticsearch_dsl import Search, Q, SF


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
        es_scale="30d",
        es_offset="1d",
        es_decay=0.5,
        es_weight=2.1,
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

    if unwanted_topics:
        must_not.append(match("topics", unwanted_topics))

    if unwanted_user_topics:
        must_not.append(match("content", unwanted_user_topics))
        must_not.append(match("title", unwanted_user_topics))

    must.append(exists("published_time"))
    if user_topics:
        must.append({"terms": {"topics": array_of_lowercase_topics(topics)}})

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

    full_query = {"size": count, "query": {"function_score": {}}}

    function1 = {
        # original parameters by Simon & Marcus
        "gauss": {"published_time": {"scale": es_scale, "offset": es_offset, "decay": es_decay}},
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
        .query(Q("match", title=search_terms) | Q("match", content=search_terms))
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
            SF("gauss", published_time={"scale": "30d", "offset": "7d", "decay": 0.3})
        ],
    )

    query = {"size": count, "query": weighted_query.to_dict()}

    return query
