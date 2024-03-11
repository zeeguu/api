#!/usr/bin/env python

"""

    goes through all the articles in the DB 
    by language and associates them with the
    corresponding topics
    

"""

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, TopicKeyword
from url_topics import get_topic_keywords_from_article
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
        topic_keywords = [
            TopicKeyword.find_or_create(db_session, keyword)
            for keyword in get_topic_keywords_from_article(article)
            if keyword is not None
        ]
        article.set_topic_keywords(topic_keywords)
        db_session.add(article)
    except Exception as e:
        print(f"Failed for article id: {a_id}, with: {e}")
    if counter % 1000 == 0:
        percentage = (100 * counter / total_articles) / 100
        print(
            f"{counter} dorticles done ({percentage:.4f}%). last article id: {article.id}. comitting... "
        )
        db_session.commit()
db_session.commit()
