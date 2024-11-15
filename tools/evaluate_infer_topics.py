from zeeguu.core.semantic_search import (
    add_topics_based_on_semantic_hood_search,
)

from zeeguu.core.model import Article, Language, ArticleTopicMap
from sklearn.metrics import classification_report

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch import Elasticsearch
from collections import Counter
import pandas as pd
import numpy as np

from pprint import pprint
from zeeguu.api.app import create_app

"""
    Script to evaluate the Inference of topics using a random sample of TOTAL_EXAMPLES.

    This takes articles which have been assigned a topic based on the url_keywords and
    runs the inference on them to test if inference retrieves at least one of the topics
    they have been mapped to. Usually this results in around 0.7 F1 score.
"""
np.random.seed(0)
TOTAL_EXAMPLES = 5000


app = create_app()
app.app_context().push()

es = Elasticsearch(ES_CONN_STRING)
data_collected = []


ALL_IDS = [
    a.article_id
    for a in ArticleTopicMap.query.join(Article)
    .filter(Article.language != Language.find_by_id(19))
    .filter(ArticleTopicMap.origin_type != 3)
    .all()
]


sampled_ids = np.random.choice(list(set(ALL_IDS)), TOTAL_EXAMPLES)

for i, doc_to_search in enumerate(sampled_ids):
    article_to_search = Article.find_by_id(doc_to_search)
    k_to_use = 9
    a_found_t, hits_t = add_topics_based_on_semantic_hood_search(
        article_to_search, k_to_use
    )

    neighbouring_topics = [t.topic for a in a_found_t for t in a.topics]
    neighbouring_keywords = [t.url_keyword for a in a_found_t for t in a.url_keywords]
    if len(hits_t) == 0:
        continue
    avg_score = sum([float(h["_score"]) for h in hits_t]) / len(hits_t)

    topics_counter = Counter(neighbouring_topics)
    topics_key_counter = Counter(neighbouring_keywords)
    print("----------------------------------------------")
    print("Topic Counts: ")
    pprint(topics_counter)
    print("Keyword Counts")
    pprint(topics_key_counter)
    print()
    og_topics = " ".join([str(t.topic.title) for t in article_to_search.topics])
    try:
        top_topic, count = topics_counter.most_common(1)[0]
        threshold = (
            sum(topics_counter.values()) // 2
        )  # The threshold is being at least half or above rounded down
        prediction = str(top_topic.title) if count >= threshold else ""
        print(f"Prediction: '{prediction}', Original: '{og_topics}'.")
        print(f"Pred Avg Score: {avg_score:.2f}, {len(hits_t)} K neigh.")
        print(f"Progress: {i+1}/{TOTAL_EXAMPLES}")
        data_collected.append(
            [
                i,
                article_to_search.title,
                og_topics,
                prediction,
                prediction in og_topics and prediction != "",
                (
                    prediction
                    if prediction in og_topics and prediction != ""
                    else og_topics
                ),
                article_to_search.language.name,
            ]
        )
    except Exception as e:
        data_collected.append(
            [
                i,
                article_to_search.title,
                og_topics,
                "",
                False,
                og_topics,
                article_to_search.language.name,
            ]
        )

df = pd.DataFrame(
    data_collected,
    columns=[
        "id",
        "title",
        "topic_url",
        "topic_inferred",
        "is_correct",
        "topic_found",
        "language",
    ],
)
print(classification_report(df["topic_found"], df["topic_inferred"]))
print(df["language"].value_counts())
