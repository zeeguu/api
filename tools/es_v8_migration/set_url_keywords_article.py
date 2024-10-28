#!/usr/bin/env python

"""
    Populates the url_keywords based on the existing articles of the DB.
    This is the first step of the migration to introduce the url_keywords based topics.
"""

import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, UrlKeyword
from zeeguu.core.model.article_url_keyword_map import ArticleUrlKeywordMap
from url_topics import get_url_keywords_from_article
from tqdm import tqdm

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session

counter = 0

# languages = Language.available_languages()
print("Adding topics keywords to articles!")
already_extraced_articles = set(
    [a_id[0] for a_id in db_session.query(ArticleUrlKeywordMap.article_id).all()]
)
all_article_id = [
    a_id[0]
    for a_id in db_session.query(Article.id).all()
    if a_id[0] not in already_extraced_articles
]
print(f"Filered a total of: {len(already_extraced_articles)}")
total_articles = len(all_article_id)
for a_id in tqdm(all_article_id):
    counter += 1
    try:
        article = Article.find_by_id(a_id)
        url_keywords = [
            UrlKeyword.find_or_create(db_session, keyword, article.language)
            for keyword in get_url_keywords_from_article(article)
            if keyword is not None
        ]
        article.set_url_keywords(url_keywords, db_session)
        db_session.add(article)
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
