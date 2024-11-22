from zeeguu.core.semantic_search import (
    articles_like_this_semantic,
    add_topics_based_on_semantic_hood_search,
    articles_like_this_tfidf,
    find_articles_based_on_text,
)

from zeeguu.core.model.article import Article
from zeeguu.core.model.url_keyword import UrlKeyword

from zeeguu.core.elastic.settings import ES_CONN_STRING
from elasticsearch import Elasticsearch
from collections import Counter

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
parser.add_argument("-a", "--article_id", type=int, help="article id to search with")
parser.add_argument("-k", "--keyword", type=str, help="keyword to search with")


def search_similar_to_article(article_id):
    app = create_app()
    app.app_context().push()
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
            f"{hit["_id"]} {hit["_score"]:.4f} {hit["_source"]["language"]}, Topics: {hit['_source']['topics']} {hit["_source"].get("url_keywords", [])} {hit["_source"].get("url", "")}"
        )

    print()
    print("Similar articles to classify:")
    for hit in hits_t:
        print(
            f"{hit["_id"]} {hit["_score"]:.4f} {hit["_source"]["language"]}, Topics: {hit['_source']['topics']} {hit["_source"].get("url_keywords", [])} {hit["_source"].get("url", "")}"
        )
    print()
    print("More like this articles!:")
    for hit in hits_lt:
        print(
            f"{hit["_id"]} {hit["_score"]:.4f} {hit["_source"]["language"]}, Topics: {hit['_source']['topics']} {hit["_source"].get("url_keywords", [])} {hit["_source"].get("url", "")}"
        )
    neighbouring_topics = [t.topic.title for a in a_found_t for t in a.topics]
    TOPICS_TO_NOT_COUNT = UrlKeyword.EXCLUDE_TOPICS
    neighbouring_keywords = [
        t.url_keyword
        for a in a_found_t
        for t in a.url_keywords
        if t.url_keyword.keyword not in TOPICS_TO_NOT_COUNT
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
    print("Title: ", article_to_search.title[:100])
    print("Content: ", article_to_search.content[:100])
    print()
    print("Top match content (sim): ")
    print(a_found_t[0].content[:100])
    print("Top match content (sim, same lang): ")
    print(a_found[0].content[:100])


def search_similar_to_keyword(keyword):
    app = create_app()
    app.app_context().push()

    es = Elasticsearch(ES_CONN_STRING)

    a_found, hits = find_articles_based_on_text(keyword)
    print("------------------------------------------------")

    print("Keyword Searched: ", keyword)
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
    print("Article list: ")
    print(a_found)


if __name__ == "__main__":
    args = parser.parse_args()
    article_id = args.article_id
    keyword = args.keyword
    if article_id:
        search_similar_to_article(article_id)
    if keyword:
        search_similar_to_keyword(keyword)
