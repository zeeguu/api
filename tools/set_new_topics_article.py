#!/usr/bin/env python

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.content_retriever.article_downloader import add_topics
from zeeguu.core.model.article import Article
from tqdm import tqdm


"""
    Script to add inferred topics to articles with no label.

    If we want to add the new topics to articles that haven't been lable this script
    will go through the list of articles and if no NewTopics are found it will run the
    add_new_topics, assigning topics based on url_keywords, hardcoded or inferred.
"""

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
        if len(article.topics) > 0:
            print("This article already has topics!")
            continue
        add_topics(
            article,
            article.feed,
            [auk.url_keyword for auk in article.url_keywords],
            db_session,
        )
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
