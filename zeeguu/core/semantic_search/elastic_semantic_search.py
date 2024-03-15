from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q, SF

from zeeguu.core.model import (
    Article,
)

from zeeguu.core.elastic.elastic_query_builder import (
    build_elastic_semantic_sim_query,
    build_elastic_semantic_sim_query_for_topic_cls,
    more_like_this_query,
)
from zeeguu.core.util.timer_logging_decorator import time_this
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.semantic_vector_api import get_embedding_from_article


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
def like_this_from_article(article: Article):
    query_body = more_like_this_query(10, article.content, article.language, 100, 0)
    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)
    final_article_mix = []
    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    return [a for a in final_article_mix if a is not None and not a.broken], hit_list


@time_this
def semantic_search_from_article(article: Article):
    query_body = build_elastic_semantic_sim_query(
        11,
        "",
        "",
        None,
        "",
        "",
        article.language,
        100,
        0,
        get_embedding_from_article(article),
        article,
        es_scale="3d",
        es_decay=0.8,
        es_weight=4.2,
        second_try=False,
    )
    final_article_mix = []

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    return [a for a in final_article_mix if a is not None and not a.broken], hit_list


@time_this
def semantic_search_add_topics_based_on_neigh(article: Article):
    query_body = build_elastic_semantic_sim_query_for_topic_cls(
        7,
        "",
        "",
        "",
        "",
        "",
        "",
        100,
        0,
        semantic_embedding_model.get_vector(article.content),
        article,
        es_scale="3d",
        es_decay=0.8,
        es_weight=4.2,
        second_try=False,
    )
    final_article_mix = []

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    return [a for a in final_article_mix if a is not None and not a.broken], hit_list


def _to_articles_from_ES_hits(hits):
    articles = []
    for hit in hits:
        articles.append(Article.find_by_id(hit.get("_id")))
    return articles
