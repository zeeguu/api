from zeeguu.core.semantic_search import (
    semantic_search_from_article,
    semantic_search_add_topics_based_on_neigh,
    like_this_from_article,
)

from zeeguu.core.model.article import Article
from zeeguu.api.app import create_app

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch import Elasticsearch
from collections import Counter

from pprint import pprint

app = create_app()
app.app_context().push()

es = Elasticsearch(ES_CONN_STRING)
# stats = es.indices.stats(index=ES_ZINDEX)
# pprint(stats)

doc_to_search = 2440969
article_to_search = Article.find_by_id(doc_to_search)
a_found, hits = semantic_search_from_article(article_to_search)
print("------------------------------------------------")
a_found_t, hits_t = semantic_search_add_topics_based_on_neigh(article_to_search)
a_found_lt, hits_lt = like_this_from_article(article_to_search)


print("Doc Searched: ", doc_to_search)
print("Similar articles:")
for hit in hits:
    print(
        hit["_id"],
        hit["_source"]["topics"],
        hit["_source"]["language"],
        hit["_source"].get("topic_keywords", []),
        hit["_source"].get("url", ""),
        hit["_score"],
    )

print("Similar articles to classify:")
for hit in hits_t:
    print(
        hit["_id"],
        hit["_source"]["topics"],
        hit["_source"]["language"],
        hit["_source"].get("topic_keywords", []),
        hit["_source"].get("url", ""),
        hit["_score"],
    )

print("More like this articles!:")
for hit in hits_lt:
    print(
        hit["_id"],
        hit["_source"]["topics"],
        hit["_source"]["language"],
        hit["_source"].get("topic_keywords", []),
        hit["_source"].get("url", ""),
        hit["_score"],
    )
neighbouring_topics = [t.title for a in a_found_t for t in a.topics]
TOPICS_TO_NOT_COUNT = set(["news", "aktuell", "nyheder", "nieuws", "article"])
neighbouring_keywords = [
    t.topic_keyword.keyword
    for a in a_found_t
    for t in a.topic_keywords
    if t.topic_keyword.keyword not in TOPICS_TO_NOT_COUNT
]
print(neighbouring_keywords)
topics_counter = Counter(neighbouring_topics)
topics_key_counter = Counter(neighbouring_keywords)
print(topics_counter)
print("Classification: ", topics_counter.most_common(1)[0])
print(topics_key_counter)
print("Classification: ", topics_key_counter.most_common(1)[0])
print(article_to_search.title[:100])
print(article_to_search.content[:100])
print("Top match content (sim): ")
print(a_found_t[0].content[:100])
print("Top match content (sim, same lang): ")
print(a_found[0].content[:100])
