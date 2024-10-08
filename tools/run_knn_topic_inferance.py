from zeeguu.core.semantic_search import (
    articles_like_this_semantic,
    add_topics_based_on_semantic_hood_search,
    articles_like_this_tfidf,
)

from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch import Elasticsearch
from collections import Counter
from zeeguu.core.elastic.elastic_query_builder import build_elastic_recommender_query

from zeeguu.api.app import create_app
import argparse

"""
    Runs the different ES similarity queries for a particular article. Can be used
    to investigate what articles were used to perform the Topic Inference and see the 
    limitations of the various aproaches.
"""

parser = argparse.ArgumentParser(
    description="Utilizes the various similar document queries in ES, to analyze the results."
)
parser.add_argument("article_id", type=int, help="article id to search with")


def search_similar_to_article(article_id):
    app = create_app()
    app.app_context().push()

    es = Elasticsearch(ES_CONN_STRING)

    doc_to_search = article_id
    article_to_search = Article.find_by_id(doc_to_search)

    a_found, hits = articles_like_this_semantic(article_to_search)
    print("------------------------------------------------")
    a_found_t, hits_t = add_topics_based_on_semantic_hood_search(article_to_search)
    a_found_lt, hits_lt = articles_like_this_tfidf(article_to_search)

    print("Doc Searched: ", doc_to_search)
    print()
    print("Similar articles:")
    for hit in hits:
        print(
            hit["_id"],
            hit["_source"]["old_topics"],
            hit["_source"]["language"],
            f"New Topics: {hit['_source']['topics']}",
            hit["_source"].get("url_keywords", []),
            hit["_source"].get("url", ""),
            hit["_score"],
        )

    print()
    print("Similar articles to classify:")
    for hit in hits_t:
        print(
            hit["_id"],
            hit["_source"]["old_topics"],
            hit["_source"]["language"],
            f"New Topics: {hit['_source']['topics']}",
            hit["_source"].get("url_keywords", []),
            hit["_source"].get("url", ""),
            hit["_score"],
        )
    print()
    print("More like this articles!:")
    for hit in hits_lt:
        print(
            hit["_id"],
            hit["_source"]["old_topics"],
            hit["_source"]["language"],
            f"New Topics: {hit['_source']['topics']}",
            hit["_source"].get("url_keywords", []),
            hit["_source"].get("url", ""),
            hit["_score"],
        )
    neighbouring_topics = [t.new_topic for a in a_found_t for t in a.new_topics]
    TOPICS_TO_NOT_COUNT = set(["news", "aktuell", "nyheder", "nieuws", "article"])
    neighbouring_keywords = [
        t.url_keywords
        for a in a_found_t
        for t in a.url_keywords
        if t.url_keywords.keyword not in TOPICS_TO_NOT_COUNT
    ]

    print()
    print(neighbouring_keywords)
    topics_counter = Counter(neighbouring_topics)
    topics_key_counter = Counter(neighbouring_keywords)
    print(topics_counter)
    print("Classification: ", topics_counter.most_common(1)[0])
    print(topics_key_counter)
    print("Classification: ", topics_key_counter.most_common(1)[0])
    print()
    print(article_to_search.title[:100])
    print(article_to_search.content[:100])
    print("Top match content (sim): ")
    print(a_found_t[0].content[:100])
    print("Top match content (sim, same lang): ")
    print(a_found[0].content[:100])


if __name__ == "__main__":
    args = parser.parse_args()
    article_id = args.article_id
    search_similar_to_article(article_id)
