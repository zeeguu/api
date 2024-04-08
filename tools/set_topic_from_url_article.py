#!/usr/bin/env python

"""

    goes through all the articles in the DB 
    by language and associates them with the
    corresponding topics
    

"""

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, NewTopic
from tqdm import tqdm

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

counter = 0

# languages = Language.available_languages()
print("Adding topics keywords to articles!")
all_article_id = [a_id[0] for a_id in db_session.query(Article.id).all()]
total_articles = len(all_article_id)
for a_id in tqdm(all_article_id):
    counter += 1
    try:
        article = Article.find_by_id(a_id)
        topics = []
        topics_added = set()
        for topic_key in article.topic_keywords:
            topic = topic_key.topic_keyword.topic
            if topic is None:
                continue
            if topic.id in topics_added:
                continue
            topics_added.add(topic.id)
            topics.append(topic)
        article.set_new_topics(topics)
        db_session.add(article)
    except Exception as e:
        counter -= 1
        print(f"Failed for article id: {a_id}, with: {e}")
    if counter % 1000 == 0:
        percentage = (100 * counter / total_articles) / 100
        print(
            f"{counter} dorticles done ({percentage:.4f}%). last article id: {article.id}. comitting... "
        )
        db_session.commit()
db_session.commit()
