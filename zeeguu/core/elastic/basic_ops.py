from elasticsearch import Elasticsearch

from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX


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
