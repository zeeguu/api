"""
    This script expects the following parameters:

    - URL_KEYWORD_TO_UPDATE (str): the keyword we seek to update the ES
    - DELETE_ARTICLE_NEW_TOPICS (bool): if we should delete the current new topics for
    the articles containing the URL_KEYWORD_TO_UPDATE. e.g. we note that there is a 
    keyword wrongly associated with a specific topic.
    - RECALCULATE_TOPICS (bool): if the topics for the articles should be recalculated.
    Let's say two keywords have the same topic, then the article would loose it's topic 
    despite still being categorized by another keyword. E.g. 'vejret' and 'klima' are 
    associated with 'Technology & Science'. If we delete topics associated, with 'vejret' 
    all articles with 'vejret' will loose that topic. This would be incorrect for all 
    those that continue to have 'klima' as a keyword. For this reason, 
    RECALCULATE_TOPICS should be true. This setting MUST BE true, in case of an update,
    e.g. we adde a new mapping to one of the keywords.
    - RE_INDEX_ONLY_ARTICLES_IN_ES (bool): if the articles re-index are only those 
    that were already in ES.
    - ITERATION_STEP (int): number of articles to index in each loop. 
"""

URL_KEYWORD_TO_UPDATE = "vejret"
DELETE_ARTICLE_NEW_TOPICS = True
RECALCULATE_TOPICS = True
RE_INDEX_ONLY_ARTICLES_IN_ES = True
ITERATION_STEP = 1000


# coding=utf-8
from zeeguu.core.elastic.indexing import (
    create_or_update_bulk_docs,
)

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
import zeeguu.core
from zeeguu.core.model import Article
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.app import create_app

from zeeguu.core.model import (
    ArticleUrlKeywordMap,
    UrlKeyword,
    NewArticleTopicMap,
    NewTopic,
)

from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING
import numpy as np
from tqdm import tqdm

app = create_app()
app.app_context().push()


es = Elasticsearch(ES_CONN_STRING)
db_session = zeeguu.core.model.db.session
print(es.info())


def ids_of_articles_matching_url_keyword():
    return np.array(
        [
            a_id[0]
            for a_id in db_session.query(Article.id)
            .join(ArticleUrlKeywordMap)
            .join(UrlKeyword)
            .filter(UrlKeyword.keyword == URL_KEYWORD_TO_UPDATE)
            .distinct()
        ]
    )


def main():
    def fetch_articles_by_id(id_list, recalculate_topic=False):
        for i in id_list:
            try:
                article = Article.find_by_id(i)
                if not article:
                    print(f"Skipped for: '{i}', article not in DB.")
                    continue
                if recalculate_topic:
                    article.recalculate_topics_from_url_keywords(db_session)
                    db_session.commit()
                yield article
            except NoResultFound:
                print(f"fail for: '{i}'")
            except Exception as e:
                print(f"fail for: '{i}', {e}")

    def gen_docs(articles_w_topics):
        for article in articles_w_topics:
            try:
                yield create_or_update_bulk_docs(article, db_session)
            except Exception as e:
                print(f"fail for: '{article.id}', {e}")

    # Get the articles for the url_keyword
    target_ids = ids_of_articles_matching_url_keyword()

    print(
        f"Got articles for url_keyword '{URL_KEYWORD_TO_UPDATE}', total: {len(target_ids)}",
    )

    # Updating url_keyword new_topic mapping
    # And the topics that were added based on that keyword.
    if DELETE_ARTICLE_NEW_TOPICS:
        new_topics_ids_to_delete = []
        new_topics = []
        url_keywords = UrlKeyword.find_all_by_keyword(URL_KEYWORD_TO_UPDATE)
        for u_key in url_keywords:
            if u_key.new_topic_id:
                new_topics.append(NewTopic.find_by_id(u_key.new_topic_id))
                new_topics_ids_to_delete.append(u_key.new_topic_id)
                u_key.new_topic_id = None

        print(
            f"Deleting new_topics '{",".join([t.title for t in new_topics])}' for articles which have the keyword: '{URL_KEYWORD_TO_UPDATE}'"
        )
        topic_mappings_to_delete = NewArticleTopicMap.query.filter(
            NewArticleTopicMap.article_id.in_(list(target_ids))
        ).filter(NewArticleTopicMap.new_topic_id.in_(new_topics_ids_to_delete))
        print(
            f"Found '{len(topic_mappings_to_delete.all())}' topic mappings to delete."
        )
        topic_mappings_to_delete.delete()
        db_session.commit()
        print("MySQL deletion completed.")

    if len(target_ids) == 0:
        print("No articles found! Exiting...")
        return

    # I noticed that if a document is not added then it won't let me query the ES search.
    if RE_INDEX_ONLY_ARTICLES_IN_ES:
        print("Re-indexing only existing articles in ES...")
        es_query = {"query": {"match_all": {}}}
        ids_in_es = set(
            [int(hit["_id"]) for hit in scan(es, index=ES_ZINDEX, query=es_query)]
        )
        target_ids_in_es = list(filter(lambda x: x in ids_in_es, target_ids))
        if len(target_ids_in_es) < len(target_ids):
            print(
                f"From the total articles {len(target_ids)}, only {len(target_ids_in_es)} will be indexed..."
            )
            target_ids = target_ids_in_es

    total_added = 0
    errors_encountered = []
    print("Starting re-indexing process...")
    for i_start in tqdm(range(0, len(target_ids), ITERATION_STEP)):
        batch = target_ids[i_start : i_start + ITERATION_STEP]
        res_bulk, error_bulk = bulk(
            es,
            gen_docs(fetch_articles_by_id(batch, RECALCULATE_TOPICS)),
            raise_on_error=False,
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
