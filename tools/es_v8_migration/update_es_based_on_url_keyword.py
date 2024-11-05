"""
    This script expects the following parameters:

    - URL_KEYWORD_TO_UPDATE (str): the keyword we seek to update the ES
    - DELETE_ARTICLE_NEW_TOPICS (bool): if we should delete the current new topics for
    the articles containing the URL_KEYWORD_TO_UPDATE. e.g. we note that there is a 
    keyword wrongly associated with a specific topic.
    - ITERATION_STEP (int): number of articles to index in each loop. 
"""

URL_KEYWORD_TO_UPDATE = "vejret"
DELETE_ARTICLE_NEW_TOPICS = True
ITERATION_STEP = 100


# coding=utf-8
from zeeguu.core.elastic.indexing import (
    create_or_update_bulk_docs,
)
from sqlalchemy import func
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import bulk
import zeeguu.core
from zeeguu.core.model import Article
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.app import create_app

from zeeguu.core.model import (
    Topic,
    ArticleUrlKeywordMap,
    UrlKeyword,
    NewArticleTopicMap,
)
from zeeguu.core.model.article import article_topic_map
from zeeguu.core.elastic.settings import ES_CONN_STRING
import numpy as np
from tqdm import tqdm

app = create_app()
app.app_context().push()


print(ES_CONN_STRING)
es = Elasticsearch(ES_CONN_STRING)
db_session = zeeguu.core.model.db.session
print(es.info())


def find_topics(article_id, session):
    article_topic = (
        session.query(Topic)
        .join(article_topic_map)
        .filter(article_topic_map.c.article_id == article_id)
    )
    topics = ""
    for t in article_topic:
        topics = topics + str(t.title) + " "

    return topics.rstrip()


def main():
    def fetch_articles_by_id(id_list):
        for i in id_list:
            try:
                article = Article.find_by_id(i)
                if not article:
                    print(f"Skipped for: '{i}', article not in DB.")
                    continue
                topics = find_topics(article.id, db_session)
                yield (article, topics)
            except NoResultFound:
                print(f"fail for: '{i}'")
            except Exception as e:
                print(f"fail for: '{i}', {e}")

    def gen_docs(articles_w_topics):
        for article, topics in articles_w_topics:
            try:
                yield create_or_update_bulk_docs(article, db_session, topics)
            except Exception as e:
                print(f"fail for: '{article.id}', {e}")

    # Get the articles for the url_keyword
    target_ids = np.array(
        [
            a_id[0]
            for a_id in db_session.query(Article.id)
            .join(ArticleUrlKeywordMap)
            .join(UrlKeyword)
            .filter(UrlKeyword.keyword == URL_KEYWORD_TO_UPDATE)
            .distinct()
        ]
    )

    print(
        f"Got articles with url_keyword '{URL_KEYWORD_TO_UPDATE}', total: {len(target_ids)}",
    )

    if DELETE_ARTICLE_NEW_TOPICS:
        print(
            f"Deleting new_topics for articles with the keyword: '{URL_KEYWORD_TO_UPDATE}'"
        )
        articles_to_delete = NewArticleTopicMap.query.filter(
            NewArticleTopicMap.article_id.in_(list(target_ids))
        )
        articles_to_delete.delete()
        db_session.commit()

    if len(target_ids) == 0:
        print("No articles found! Exiting...")
        return

    # I noticed that if a document is not added then it won't let me query the ES search.
    total_added = 0
    errors_encountered = []

    for i_start in tqdm(range(0, len(target_ids), ITERATION_STEP)):
        batch = target_ids[i_start : i_start + ITERATION_STEP]
        res_bulk, error_bulk = bulk(
            es, gen_docs(fetch_articles_by_id(batch)), raise_on_error=False
        )
        total_added += res_bulk
        errors_encountered += error_bulk
        total_bulk_errors = len(error_bulk)
        if total_bulk_errors > 0:
            print(f"## Warning, {total_bulk_errors} failed to index. With errors: ")
            print(error_bulk)
        db_session.commit()
        print(f"Batch finished. ADDED/UPDATED:{res_bulk} | ERRORS: {total_bulk_errors}")
    print(errors_encountered)
    print(f"Total articles added/updated: {total_added}")


if __name__ == "__main__":
    start = datetime.now()
    print(f"Started at: {start}")
    main()
    end = datetime.now()
    print(f"Ended at: {end}")
    print(f"Process took: {end-start}")
