from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q, SF

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
    build_elastic_semantic_sim_query,
)
from zeeguu.core.util.timer_logging_decorator import time_this
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.semantic_vector import semantic_embedding_model


@time_this
def article_semantic_search_for_user(
    user,
    count,
    search_terms,
    es_scale="3d",
    es_decay=0.8,
    es_weight=4.2,
):
    return NotImplementedError

    final_article_mix = []

    (
        language,
        upper_bounds,
        lower_bounds,
        topics_to_include,
        topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
    ) = prepare_user_constraints(user)

    # build the query using elastic_query_builder
    query_body = build_elastic_semantic_sim_query(
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


@time_this
def article_semantic_search_for_article(article: Article):
    query_body = build_elastic_semantic_sim_query(
        20,
        "",
        "",
        "",
        "",
        "",
        article.language,
        100,
        0,
        semantic_embedding_model.get_vector(article.content),
        es_scale="3d",
        es_decay=0.8,
        es_weight=4.2,
        second_try=False,
        k=5,
    )
    final_article_mix = []

    print(ES_CONN_STRING)
    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)

    print(res)
    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    return [a for a in final_article_mix if a is not None and not a.broken]


def _to_articles_from_ES_hits(hits):
    articles = []
    for hit in hits:
        articles.append(Article.find_by_id(hit.get("_id")))
    return articles
