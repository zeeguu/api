# coding=utf-8
import sqlalchemy as database
from zeeguu.core.elastic.indexing import create_or_update, document_from_article
from sqlalchemy import func
from elasticsearch import Elasticsearch
import zeeguu.core
from sqlalchemy.orm import sessionmaker
from zeeguu.core.model import Article
import sys
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.elastic.settings import ES_ZINDEX, ES_CONN_STRING

es = Elasticsearch([ES_CONN_STRING])
DB_URI = zeeguu.core.app.config["SQLALCHEMY_DATABASE_URI"]
engine = database.create_engine(DB_URI)
Session = sessionmaker(bind=engine)
session = Session()


def main(starting_index):

    max_id = session.query(func.max(Article.id)).first()[0]
    min_id = session.query(func.min(Article.id)).first()[0]
    print(f"starting import at: {starting_index}")
    print(f"max id in db: {max_id}")

    for i in range(max_id, min_id,-1):
        print("article id...")
        print(i)
        try:
            article = Article.find_by_id(i)
            if article:
                print(article.title)
                print(article.id)
                res = create_or_update(article, session)
                print(res)
        except NoResultFound:
            print(f"fail for: {i}")
        except:
            print("fail for " + str(i))
            # import traceback
            # traceback.print_exc()


if __name__ == "__main__":


    print("waiting for the ES process to boot up")
  
    print(f"started at: {datetime.now()}")
    starting_index = 0
    

    if len(sys.argv) > 1:
        starting_index = int(sys.argv[1])

    main(starting_index)
    print(f"ended at: {datetime.now()}")
