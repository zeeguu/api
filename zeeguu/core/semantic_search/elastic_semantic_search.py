from elasticsearch import Elasticsearch
from elastic_transport import ConnectionError

from zeeguu.core.model import (
    Article,
)

from zeeguu.core.elastic.elastic_query_builder import (
    build_elastic_semantic_sim_query_for_article,
    build_elastic_semantic_sim_query_for_topic_cls,
    build_elastic_semantic_sim_query_for_text,
    more_like_this_query,
)
from zeeguu.core.content_recommender.elastic_recommender import (
    _to_articles_from_ES_hits,
)
from zeeguu.core.util.timer_logging_decorator import time_this
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.semantic_vector_api import (
    get_embedding_from_article,
    get_embedding_from_text,
)


@time_this
def article_semantic_search_for_user(
    user,
    count,
    search_terms,
):
    return NotImplementedError


@time_this
def articles_like_this_tfidf(article: Article):
    query_body = more_like_this_query(10, article.get_content(), article.language)
    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)
    final_article_mix = []
    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    return [a for a in final_article_mix if a is not None and not a.broken], hit_list


@time_this
def articles_like_this_semantic(article: Article):
    query_body = build_elastic_semantic_sim_query_for_article(
        10, article.language, get_embedding_from_article(article), article
    )
    final_article_mix = []

    try:
        es = Elasticsearch(ES_CONN_STRING)
        res = es.search(index=ES_ZINDEX, body=query_body)

        hit_list = res["hits"].get("hits")
        final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

        return [
            a for a in final_article_mix if a is not None and not a.broken
        ], hit_list
    except ConnectionError:
        print("Could not connect to ES server.")
    except Exception as e:
        print(f"Error encountered: {e}")
    return [], []


def get_article_w_topics_based_on_text_similarity(text, k: int = 9, filter_ids=None):

    if filter_ids is None:
        filter_ids = []

    embedding = get_embedding_from_text(text)
    if embedding is None:
        # Embedding service unavailable, return empty results
        return [], []
        
    query_body = build_elastic_semantic_sim_query_for_topic_cls(
        k, embedding, filter_ids=filter_ids
    )
    final_article_mix = []

    try:
        es = Elasticsearch(ES_CONN_STRING)
        res = es.search(index=ES_ZINDEX, body=query_body)

        hit_list = res["hits"].get("hits")
        final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

        return [
            a for a in final_article_mix if a is not None and not a.broken
        ], hit_list
    except ConnectionError:
        print("Could not connect to ES server.")
    except Exception as e:
        print(f"Error encountered: {e}")
    return [], []


def get_topic_classification_based_on_similar_content(
    text,
    k: int = 9,
    filter_ids: list[int] = None,
    verbose=False,
):
    from collections import Counter

    if filter_ids is None:
        filter_ids = []

    found_articles, _ = get_article_w_topics_based_on_text_similarity(
        text, k, filter_ids=filter_ids
    )
    neighbouring_topics = [t.topic for a in found_articles for t in a.topics]
    if len(neighbouring_topics) > 0:
        topics_counter = Counter(neighbouring_topics)

        if verbose:
            from pprint import pprint

            pprint(topics_counter)

        top_topic, count = topics_counter.most_common(1)[0]
        threshold = (
            sum(topics_counter.values()) // 2
        )  # The threshold is being at least half or above rounded down

        if count >= threshold:
            if verbose:
                print(f"Used INFERRED: {top_topic}, {count}, with t={threshold}")
            return top_topic
    return None


@time_this
def find_articles_based_on_text(text, k: int = 9):  # hood = (slang) neighborhood
    query_body = build_elastic_semantic_sim_query_for_text(
        k, get_embedding_from_text(text)
    )
    final_article_mix = []

    try:
        es = Elasticsearch(ES_CONN_STRING)
        res = es.search(index=ES_ZINDEX, body=query_body)

        hit_list = res["hits"].get("hits")
        final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

        return [
            a for a in final_article_mix if a is not None and not a.broken
        ], hit_list
    except ConnectionError:
        print("Could not connect to ES server.")
    except Exception as e:
        print(f"Error encountered: {e}")
    return [], []
