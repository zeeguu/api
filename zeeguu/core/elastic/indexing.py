from zeeguu.core.model import UrlKeyword, Topic
from zeeguu.core.model.article_url_keyword_map import ArticleUrlKeywordMap
from zeeguu.core.model.article_topic_map import TopicOriginType, ArticleTopicMap

from elasticsearch import Elasticsearch
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.elastic.basic_ops import es_update, es_index, es_exists, es_delete
from zeeguu.core.semantic_vector_api import (
    get_embedding_from_article,
    get_embedding_from_video,
)
from zeeguu.core.model.video_topic_map import VideoTopicMap
from zeeguu.core.model.video import MAX_CHAR_COUNT_IN_SUMMARY
from elasticsearch_dsl import Search, Q


def get_doc_in_es(es_id: str, get_source_dict=True, verbose=False):
    """
    Provides a document source (or the doc object) by ES id.
    Zeeguu used to use article_ids as a way to index articles, but we have changed to
    allowing ES to auto assign documents. It seems the generated ids can be alphanumeric,
    resembling hashes rather than integers.
    """
    es = Elasticsearch(ES_CONN_STRING)
    if es.exists(index=ES_ZINDEX, id=es_id):
        doc = es.get(index=ES_ZINDEX, id=es_id)
        return doc["_source"] if get_source_dict else doc
    else:
        if verbose:
            print(f"ES doc with id: '{es_id}' not found")
        return None


def get_article_hit_in_es(article_id, verbose=False):
    """
    Returns the article from ElasticSearch. The DSL returns a hit object, which can
    be coverted to a dict using the .to_dict() method. However, the hit object
    can be used as an object with the keys as attributes, it also features "in"
    so something like:
     >>> "article_id" in hit
     >   True
    """
    es = Elasticsearch(ES_CONN_STRING)
    s = Search(using=es, index=ES_ZINDEX).query("match", article_id=article_id)
    response = s.execute()
    if len(response) > 1:
        print(f"WARNING: More than one document found for article id: {article_id}...")
        if verbose:
            print(f"Returning the first match...")
    elif len(response) == 0:
        if verbose:
            print(f"No document found for article id: {article_id}...")
    return response[0] if len(response) >= 1 else None


def find_topics_article(article_id, session):
    article_topics = (
        session.query(Topic)
        .join(ArticleTopicMap)
        .filter(ArticleTopicMap.article_id == article_id)
        .filter(ArticleTopicMap.origin_type != TopicOriginType.INFERRED.value)
        .all()
    )
    inferred_article_topics = (
        session.query(Topic)
        .join(ArticleTopicMap)
        .filter(ArticleTopicMap.article_id == article_id)
        .filter(ArticleTopicMap.origin_type == TopicOriginType.INFERRED.value)
        .all()
    )
    return article_topics, inferred_article_topics


def find_topics_video(video_id, session):
    video_topics = (
        session.query(Topic)
        .join(VideoTopicMap)
        .filter(VideoTopicMap.video_id == video_id)
        .filter(VideoTopicMap.origin_type != TopicOriginType.INFERRED.value)
        .all()
    )
    inferred_video_topics = (
        session.query(Topic)
        .join(VideoTopicMap)
        .filter(VideoTopicMap.video_id == video_id)
        .filter(VideoTopicMap.origin_type == TopicOriginType.INFERRED.value)
        .all()
    )
    return video_topics, inferred_video_topics


def find_filter_url_keywords(article_id, session):
    article_url_keywords = (
        session.query(UrlKeyword)
        .join(ArticleUrlKeywordMap)
        .filter(ArticleUrlKeywordMap.article_id == article_id)
    )
    topic_kewyords = [
        str(t_key.keyword)
        for t_key in article_url_keywords
        if t_key not in UrlKeyword.EXCLUDE_TOPICS
    ]
    return topic_kewyords


def document_from_video(video, session, current_doc=None):
    topics, topics_inferred = find_topics_video(video.id, session)
    embedding_generation_required = True
    video_text = video.get_content()
    summary = video_text[:MAX_CHAR_COUNT_IN_SUMMARY]
    doc = {
        "video_id": video.id,
        "source_id": video.source_id,
        "title": video.title,
        "channel": video.channel.name,
        "content": video_text,
        "summary": summary,
        "description": video.description,
        "word_count": video.source.word_count,
        "published_time": video.published_time,
        "crawled_time": video.crawled_at,
        "topics": [t.title for t in topics],
        "topics_inferred": [t.title for t in topics_inferred],
        "language": video.language.name,
        "fk_difficulty": video.source.fk_difficulty,
    }
    if not embedding_generation_required and current_doc is not None:
        doc["sem_vec"] = current_doc["sem_vec"]
    else:
        doc["sem_vec"] = get_embedding_from_video(video)

    return doc


def document_from_article(article, session, current_doc=None):
    topics, topics_inferred = find_topics_article(article.id, session)
    embedding_generation_required = current_doc is None
    # Embeddings only need to be re-computed if the document
    # doesn't exist or the text is updated.
    # This is the most expensive operation in the indexing process, so it
    # saves time by skipping it.
    if current_doc is not None:
        embedding_generation_required = current_doc["content"] != article.get_content()
    doc = {
        "article_id": article.id,
        "source_id": article.source_id,
        "title": article.title,
        "author": article.authors,
        "content": article.get_content(),
        "summary": article.summary,
        "word_count": article.get_word_count(),
        "published_time": article.published_time,
        "topics": [t.title for t in topics],
        # We need to avoid using these as a way to classify further documents
        # (we should rely on the human labels to classify further articles)
        # rather than infer on inferences.
        "topics_inferred": [t.title for t in topics_inferred],
        "language": article.language.name,
        "fk_difficulty": article.get_fk_difficulty(),
        "url": article.url.as_string(),
        "video": article.video,
    }
    if not embedding_generation_required and current_doc is not None:
        doc["sem_vec"] = list(current_doc["sem_vec"])
    else:
        doc["sem_vec"] = get_embedding_from_article(article)
    return doc


def create_or_update_article(article, session):

    pre_existing_hit = get_article_hit_in_es(article)

    if pre_existing_hit:
        doc = document_from_article(article, session, pre_existing_hit["_source"])
        # Note, this might be replaced with delete + index given that update is for specific fields
        res = es_update(id=pre_existing_hit["_id"], body={"doc": doc})
    else:
        doc = document_from_article(article, session)
        res = es_index(body=doc)

    return res


def index_video(video, session):

    doc = document_from_video(video, session)
    res = es_index(body=doc)
    return res


def update_doc_with_source_id(hit, source_id):
    res = es_update(id=hit["_id"], body={"doc": {"source_id": source_id}})
    return res


def create_or_update_doc_for_bulk(article, session):
    doc = {}
    doc["_index"] = ES_ZINDEX
    hit = get_article_hit_in_es(article.id)
    if not hit:
        # If we don't find by article id, try by using ES id
        hit = get_doc_in_es(article.id, get_source_dict=False)
    if hit:
        doc_data = document_from_article(article, session, current_doc=hit["_source"])
        doc["_id"] = hit.meta.id if "meta" in hit else doc["_id"]
        doc["_op_type"] = "update"
        doc["_source"] = {"doc": doc_data}
    else:
        doc_data = document_from_article(article, session)
        doc["_op_type"] = "create"
        doc["_source"] = doc_data
    return doc


def index_in_elasticsearch(new_article, session):

    try:
        doc = document_from_article(new_article, session)
        es_index(doc)

    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        import traceback

        traceback.print_exc()


def remove_from_index(article):

    hit = get_article_hit_in_es(article.id)
    es_id = hit["_id"]
    if es_exists(id=es_id):
        print("Found in ES Index")
        es_delete(id=es_id)
        print("After deletion from the index.")
