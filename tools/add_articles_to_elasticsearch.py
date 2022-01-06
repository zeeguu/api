import zeeguu.core
from elasticsearch import Elasticsearch
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.elastic.converting_from_mysql import document_from_article
from zeeguu.core.model.article import Article

for article in Article.all_younger_than(13):
    try:
        print("indexing " + article.title)
        es = Elasticsearch(ES_CONN_STRING)
        doc = document_from_article(article, zeeguu.core.db.session)
        res = es.index(index=ES_ZINDEX, id=article.id, body=doc)
        print(res)
    except Exception as e:
        from sentry_sdk import capture_exception
