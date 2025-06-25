from elasticsearch import Elasticsearch

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from elasticsearch_dsl import Search, Q


def es_update(id, body):

    es = Elasticsearch(ES_CONN_STRING)

    return es.update(index=ES_ZINDEX, id=id, body=body)


def es_index(body):

    es = Elasticsearch(ES_CONN_STRING)

    return es.index(index=ES_ZINDEX, body=body)


def es_exists(id):

    es = Elasticsearch(ES_CONN_STRING)

    return es.exists(index=ES_ZINDEX, id=id)


def es_delete(id):

    es = Elasticsearch(ES_CONN_STRING)

    return es.delete(index=ES_ZINDEX, id=id)


def es_get_es_id_from_article_id(article_id):

    es = Elasticsearch(ES_CONN_STRING)

    res = Search(using=es, index=ES_ZINDEX).filter("term", article_id=article_id)
    res = res.execute()

    if len(res) > 0:
        return res[0].meta["id"]
    else:
        return None


def es_get_es_id_from_video_id(video_id):

    es = Elasticsearch(ES_CONN_STRING)

    res = Search(using=es, index=ES_ZINDEX).filter("term", video_id=video_id)
    res = res.execute()

    if len(res) > 0:
        return res[0].meta["id"]
    else:
        return None
