"""

 Recommender that uses ElasticSearch instead of mysql for searching.
 Based on mixed recommender.
 Still uses MySQL to find relations between the user and things such as:
   - topics, language and user subscriptions.

"""

from elasticsearch import Elasticsearch

from zeeguu.core.model import (
    Article,
    TopicFilter,
    TopicSubscription,
    SearchFilter,
    SearchSubscription,
    UserArticle,
    Language,
)

from zeeguu.core.elastic.elastic_query_builder import (
    build_elastic_recommender_query,
    build_elastic_search_query,
)
from zeeguu.core.util.timer_logging_decorator import time_this
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX


def _prepare_user_constraints(user):

    language = user.learned_language

    # 0. Ensure appropriate difficulty
    declared_level_min, declared_level_max = user.levels_for(language)
    lower_bounds = declared_level_min * 10
    upper_bounds = declared_level_max * 10

    # 1. Unwanted user topics
    # ==============================
    user_search_filters = SearchFilter.all_for_user(user)
    unwanted_user_topics = []
    for user_search_filter in user_search_filters:
        unwanted_user_topics.append(user_search_filter.search.keywords)
    print(f"keywords to exclude: {unwanted_user_topics}")

    # 2. Topics to exclude / filter out
    # =================================
    excluded_topics = TopicFilter.all_for_user(user)
    topics_to_exclude = [each.topic.title for each in excluded_topics]
    print(f"topics to exclude: {topics_to_exclude}")

    # 3. Topics subscribed, and thus to include
    # =========================================
    topic_subscriptions = TopicSubscription.all_for_user(user)
    topics_to_include = [
        subscription.topic.title
        for subscription in TopicSubscription.all_for_user(user)
    ]
    print(f"topics to include: {topic_subscriptions}")

    # 4. Wanted user topics
    # =========================================
    user_subscriptions = SearchSubscription.all_for_user(user)

    wanted_user_topics = []
    for sub in user_subscriptions:
        wanted_user_topics.append(sub.search.keywords)
    print(f"keywords to include: {wanted_user_topics}")

    return (
        language,
        upper_bounds,
        lower_bounds,
        _list_to_string(topics_to_include),
        _list_to_string(topics_to_exclude),
        _list_to_string(wanted_user_topics),
        _list_to_string(unwanted_user_topics),
    )


def article_recommendations_for_user(
    user,
    count,
    es_scale="3d",
    es_decay=0.8,
    es_weight=4.2,
):
    """

            Retrieve :param count articles which are equally distributed
            over all the feeds to which the :param user is registered to.

            Fails if no language is selected.

    :return:

    """

    final_article_mix = []

    (
        language,
        upper_bounds,
        lower_bounds,
        topics_to_include,
        topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
    ) = _prepare_user_constraints(user)

    # build the query using elastic_query_builder
    query_body = build_elastic_recommender_query(
        count,
        topics_to_include,
        topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
        language,
        upper_bounds,
        lower_bounds,
        es_scale,
        es_decay,
        es_weight,
    )

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    if len(final_article_mix) == 0:
        # build the query using elastic_query_builder
        query_body = build_elastic_recommender_query(
            count,
            topics_to_include,
            topics_to_exclude,
            wanted_user_topics,
            unwanted_user_topics,
            language,
            upper_bounds,
            lower_bounds,
            es_scale,
            es_decay,
            es_weight,
            second_try=True,
        )
        res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    articles = [a for a in final_article_mix if a is not None and not a.broken]

    sorted_articles = sorted(articles, key=lambda x: x.published_time, reverse=True)

    return sorted_articles


@time_this
def article_search_for_user(
    user,
    count,
    search_terms,
    es_scale="3d",
    es_decay=0.8,
    es_weight=4.2,
):

    final_article_mix = []

    (
        language,
        upper_bounds,
        lower_bounds,
        topics_to_include,
        topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
    ) = _prepare_user_constraints(user)

    # build the query using elastic_query_builder
    query_body = build_elastic_search_query(
        count,
        search_terms,
        topics_to_include,
        topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
        language,
        upper_bounds,
        lower_bounds,
        es_scale,
        es_decay,
        es_weight,
    )

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    if len(final_article_mix) == 0:
        # build the query using elastic_query_builder
        query_body = build_elastic_search_query(
            count,
            search_terms,
            topics_to_include,
            topics_to_exclude,
            wanted_user_topics,
            unwanted_user_topics,
            language,
            upper_bounds,
            lower_bounds,
            es_scale,
            es_decay,
            es_weight,
            second_try=True,
        )
        res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    return [a for a in final_article_mix if a is not None and not a.broken]


def _list_to_string(input_list):
    return " ".join([each for each in input_list]) or ""


def _to_articles_from_ES_hits(hits):
    articles = []
    for hit in hits:
        articles.append(Article.find_by_id(hit.get("_id")))
    return articles
