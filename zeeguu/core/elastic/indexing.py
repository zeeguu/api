from zeeguu.core.model import Topic
from zeeguu.core.model.article import article_topic_map
from zeeguu.core.model.difficulty_lingo_rank import DifficultyLingoRank


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


def document_from_article(article, session):
    topics = find_topics(article.id, session)

    doc = {
        "title": article.title,
        "author": article.authors,
        "content": article.content,
        "summary": article.summary,
        "word_count": article.word_count,
        "published_time": article.published_time,
        "topics": topics,
        "language": article.language.name,
        "fk_difficulty": article.fk_difficulty,
        "lr_difficulty": DifficultyLingoRank.value_for_article(article),
    }
    return doc


def index_in_elasticsearch(new_article, session):
    """
    # Saves the news article at ElasticSearch.
    # We recommend that everything is stored both in SQL and Elasticsearch
    # as ElasticSearch isn't persistent data
    try:
        if save_in_elastic:
            if new_article:
                es = Elasticsearch(ES_CONN_STRING)
                doc = document_from_article(new_article, session)
                res = es.index(index=ES_ZINDEX, id=new_article.id, body=doc)
                print("elastic res: " + res["result"])
    except Exception as e:
        capture_to_sentry(e)

        log("***OOPS***: ElasticSearch seems down?")
        if hasattr(e, "message"):
            log(e.message)
        else:
            log(e)
        continue
    """

    try:
        es = Elasticsearch(ES_CONN_STRING)
        doc = document_from_article(new_article, session)
        res = es.index(index=ES_ZINDEX, id=new_article.id, document=doc)
        print("elastic res: " + res["result"])
    except Exception as e:
        capture_to_sentry(e)

        print("***OOPS***: ElasticSearch seems down?")
        if hasattr(e, "message"):
            log(e.message)
        else:
            log(e)
        return


def remove_from_index(article):
    # delete also from the ES index
    from elasticsearch import Elasticsearch
    from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX

    es = Elasticsearch(ES_CONN_STRING)
    if es.exists(index=ES_ZINDEX, id=each.id):
        es.delete(index=ES_ZINDEX, id=each.id)
        deleted_from_es += 1
