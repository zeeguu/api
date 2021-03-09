def match(key, value):
    return {"match": {key: value}}


def exists(field):
    return {"exists": {"field": field}}


def add_to_dict(dict, key, value):
    dict.update({key: value})


def build_more_like_this_query(count, content, language):
    query_body = {"size": count, "query": {"bool": {}}}  # initial empty query

    must = []

    if language:
        more_like_this = {}
        add_to_dict(more_like_this, "fields", ["content", "title"])
        add_to_dict(more_like_this, "like", content)
        add_to_dict(more_like_this, "min_term_freq", 1)
        add_to_dict(more_like_this, "max_query_terms", 25)
        must.append({'more_like_this': more_like_this})

        must.append(match("language", language.name))

    query_body["query"]["bool"].update({"must": must})
    return query_body


def build_elastic_query(count, search_terms, topics, unwanted_topics, user_topics, unwanted_user_topics, language, upper_bounds,
                        lower_bounds):
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
                'should': [
                    {'match': {'topics': 'Sport'}},
                    {'match': {'content': 'soccer ronaldo'}},
                    {'match': {'title': 'soccer ronaldo'}}
                ],
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

    if topics:
        should.append(match("topics", topics))

    if not search_terms:
        search_terms = ""

    if not user_topics:
        user_topics = ""

    if search_terms or user_topics:
        search_string = search_terms + " " + user_topics
        should.append(match("content", search_string))
        should.append(match("title", search_string))

    if unwanted_topics:
        must_not.append(match("topics", unwanted_topics))

    if unwanted_user_topics:
        must_not.append(match("content", unwanted_user_topics))
        must_not.append(match("title", unwanted_user_topics))

    must.append(exists("published_time"))
    # add the must, must_not and should lists to the query body
    bool_query_body["query"]["bool"].update({"filter": {"range": {"fk_difficulty": {"gt": lower_bounds, "lt": upper_bounds}}}})

    bool_query_body["query"]["bool"].update({"should": should})
    bool_query_body["query"]["bool"].update({"must": must})
    bool_query_body["query"]["bool"].update({"must_not": must_not})


    full_query = {"size": count, "query": {"function_score": {}}}

    function1 = {
            "gauss": {"published_time": {
                    "scale": "365d",
                    "offset": "7d",
                    "decay": 0.3
                }
            }, "weight": 1.2
          }

    full_query["query"]["function_score"].update({"functions": [function1]})
    full_query["query"]["function_score"].update(bool_query_body)

    return full_query
