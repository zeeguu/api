#!/usr/bin/env python

"""
    goes through all the articles in the DB 
    by language and associates them with the
    corresponding topics
"""

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.content_retriever.article_downloader import add_new_topics
from zeeguu.core.model import Article
from tqdm import tqdm

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

counter = 0

# languages = Language.available_languages()
print("Adding inferred topics to articles!")
all_article_id = [a_id[0] for a_id in db_session.query(Article.id).all()]
total_articles = len(all_article_id)
for a_id in tqdm(all_article_id):
    counter += 1
    try:
        article = Article.find_by_id(a_id)
        if article is None:
            print("Skipping null article")
            continue
        if len(article.new_topics) > 0:
            print("This article already has topics!")
            continue
        add_new_topics(
            article,
            article.feed,
            [atk.topic_keyword for atk in article.topic_keywords],
            db_session,
        )
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
