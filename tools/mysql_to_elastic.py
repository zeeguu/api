# coding=utf-8
import sqlalchemy as database
from zeeguu_core.elastic.converting_from_mysql import document_from_article
from sqlalchemy import func
from elasticsearch import Elasticsearch
import zeeguu_core
from sqlalchemy.orm import sessionmaker
from zeeguu_core.model import Article
import sys
from datetime import datetime

from zeeguu_core.elastic.settings import ES_ZINDEX, ES_CONN_STRING

es = Elasticsearch([ES_CONN_STRING])
DB_URI = zeeguu_core.app.config["SQLALCHEMY_DATABASE_URI"]
engine = database.create_engine(DB_URI)
Session = sessionmaker(bind=engine)
session = Session()


def main(starting_index, article_batch_size):
    # fetch article_batch_size articles at a time, to avoid to much loaded into memory

    max_id = session.query(func.max(Article.id)).first()[0]
    print(f"max id in db: {max_id}")
    print(f"starting import at: {max_id - starting_index}")

    for i in range(starting_index, max_id, article_batch_size):

        print(i)
        for article in session.query(Article).order_by(Article.published_time.desc()).limit(article_batch_size).offset(
                i):
            try:
                doc = document_from_article(article, session)
                res = es.index(index=ES_ZINDEX, id=article.id, body=doc)
                if article.id % 1000 == 0:
                    print(res['result'] + ' ' + str(article.id))
            except Exception as e:
                print(f"something went wrong with article id {article.id}")
                print(str(e))


if __name__ == '__main__':

    print(f"started at: {datetime.now()}")
    starting_index = 0
    article_batch_size = 5000

    if len(sys.argv) > 1:
        starting_index = int(sys.argv[1])

    if len(sys.argv) > 2:
        article_batch_size = int(sys.argv[2])

    main(starting_index, article_batch_size)
    print(f"ended at: {datetime.now()}")
