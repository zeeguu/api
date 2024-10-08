#!/usr/bin/env python

""" 
    Script to populate the NewArticleTopicMap once the url_keywords have been mapped
    to a Topic. This step is required before inferring new topics for new articles.
"""

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import (
    Article,
    ArticleUrlKeywordMap,
    UrlKeyword,
    NewArticleTopicMap,
)
from tqdm import tqdm

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

counter = 0

# languages = Language.available_languages()
print("Finding all articles with Url Keywords with Topics assigned...")
print("(Articles which already have a NewTopic mapping are ignored.)")
a_url_keywords_w_new_topics = (
    db_session.query(Article.id)
    .join(ArticleUrlKeywordMap)
    .join(UrlKeyword)
    .join(NewArticleTopicMap, isouter=True)
    .filter(UrlKeyword.new_topic != None)
    .filter(NewArticleTopicMap.new_topic_id == None)
    .all()
)
print("Adding topics based on url keywords to articles...")
total_articles = len(a_url_keywords_w_new_topics)
for article in tqdm(a_url_keywords_w_new_topics):
    a_id = article[0]
    counter += 1
    try:
        article = Article.find_by_id(a_id)
        topics = []
        topics_added = set()
        for url_keyword in article.url_keywords:
            topic = url_keyword.url_keyword.new_topic
            if topic is None:
                continue
            if topic.id in topics_added:
                continue
            topics_added.add(topic.id)
            topics.append(topic)
        article.set_new_topics(topics, db_session)
    except Exception as e:
        counter -= 1
        print(f"Failed for article id: {a_id}, with: {e}")
    if counter % 1000 == 0:
        percentage = (100 * counter / total_articles) / 100
        print(
            f"{counter} articles done ({percentage:.4f}%). last article id: {article.id}. comitting... "
        )
        db_session.commit()
db_session.commit()
