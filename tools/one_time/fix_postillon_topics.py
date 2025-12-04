#!/usr/bin/env python
"""
One-time script to fix Der Postillon articles that were incorrectly tagged
with Business/Culture topics instead of Satire.

Run: python tools/one_time/fix_postillon_topics.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import Article, Topic
from zeeguu.core.model.article_topic_map import ArticleTopicMap, TopicOriginType

POSTILLON_FEED_ID = 214
SATIRE_TOPIC_ID = 8

articles = Article.query.filter(Article.feed_id == POSTILLON_FEED_ID).all()
print(f"Found {len(articles)} Der Postillon articles")

satire_topic = Topic.find_by_id(SATIRE_TOPIC_ID)
print(f"Satire topic: {satire_topic.title}")

fixed = 0
already_correct = 0

for article in articles:
    current_topics = [t.topic_id for t in article.topics]

    if current_topics == [SATIRE_TOPIC_ID]:
        already_correct += 1
        continue

    # Remove existing topic mappings
    ArticleTopicMap.query.filter(ArticleTopicMap.article_id == article.id).delete()

    # Add satire topic
    new_mapping = ArticleTopicMap(article, satire_topic, TopicOriginType.HARDSET.value)
    db.session.add(new_mapping)
    fixed += 1

db.session.commit()
print(f"Fixed: {fixed}")
print(f"Already correct: {already_correct}")
