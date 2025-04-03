from zeeguu.core.model import UrlKeyword, Topic
from zeeguu.core.model.article_url_keyword_map import ArticleUrlKeywordMap
from zeeguu.core.model.article_topic_map import TopicOriginType, ArticleTopicMap
from zeeguu.core.model.difficulty_lingo_rank import DifficultyLingoRank
from elasticsearch import Elasticsearch
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX
from zeeguu.core.semantic_vector_api import get_embedding_from_article
from zeeguu.core.model.video_topic_map import VideoTopicMap
from zeeguu.core.model.video import MAX_CHAR_COUNT_IN_SUMMARY


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


def document_from_source(source, session, current_doc=None, is_video=False):
    doc = {}
    if is_video:
        topics, topics_inferred = find_topics_video(source.id, session)
        embedding_generation_required = True
        video_text = source.get_content()
        summary = video_text[:MAX_CHAR_COUNT_IN_SUMMARY]
        doc = {
            "title": source.title,
            "channel": source.channel.name,
            "content": source.get_content(),
            "summary": summary,
            "description": source.description,
            "word_count": source.source.word_count,
            "published_time": source.published_at,
            # We need to avoid using these as a way to classify further documents
            # (we should rely on the human labels to classify further articles)
            # rather than infer on inferences.
            "topics_inferred": [t.title for t in topics_inferred],
            "language": source.language.name,
            "fk_difficulty": source.source.fk_difficulty,
            "video": int(is_video),
        }
        if not embedding_generation_required and current_doc is not None:
            doc["sem_vec"] = current_doc["sem_vec"]
        else:
            doc["sem_vec"] = get_embedding_from_article(source)
    else:
        topics, topics_inferred = find_topics_article(source.id, session)
        embedding_generation_required = current_doc is None
        # Embeddings only need to be re-computed if the document
        # doesn't exist or the text is updated.
        # This is the most expensive operation in the indexing process, so it
        # saves time by skipping it.
        if current_doc is not None:
            embedding_generation_required = (
                current_doc["content"] != source.get_content()
            )
        doc = {
            "title": source.title,
            "author": source.authors,
            "content": source.get_content(),
            "summary": source.summary,
            "word_count": source.get_word_count(),
            "published_time": source.published_time,
            "topics": [t.title for t in topics],
            # We need to avoid using these as a way to classify further documents
            # (we should rely on the human labels to classify further articles)
            # rather than infer on inferences.
            "topics_inferred": [t.title for t in topics_inferred],
            "language": source.language.name,
            "fk_difficulty": source.get_fk_difficulty(),
            "lr_difficulty": DifficultyLingoRank.value_for_article(source),
            "url": source.url.as_string(),
            "video": int(is_video),
        }
        if not embedding_generation_required and current_doc is not None:
            doc["sem_vec"] = current_doc["sem_vec"]
        else:
            doc["sem_vec"] = get_embedding_from_article(source)
    return doc


def create_or_update_article(article, session):
    es = Elasticsearch(ES_CONN_STRING)
    doc = document_from_source(article, session)

    if es.exists(index=ES_ZINDEX, id=article.id):
        es.delete(index=ES_ZINDEX, id=article.id)

    res = es.index(index=ES_ZINDEX, id=article.id, body=doc)

    return res


def create_or_update_video(video, session):
    MAX_ID_ARTICLE = 4000000
    es = Elasticsearch(ES_CONN_STRING)
    doc = document_from_source(video, session, is_video=True)
    print("Got doc: ", doc)
    if es.exists(index=ES_ZINDEX, id=MAX_ID_ARTICLE + video.id):
        es.delete(index=ES_ZINDEX, id=MAX_ID_ARTICLE + video.id)

    res = es.index(index=ES_ZINDEX, id=MAX_ID_ARTICLE + video.id, body=doc)
    print("ES RETURNED")
    print(res)
    return res


def create_or_update_doc_for_bulk(article, session):
    es = Elasticsearch(ES_CONN_STRING)
    doc_data = document_from_source(article, session)
    doc = {}
    doc["_id"] = article.id
    doc["_index"] = ES_ZINDEX
    if es.exists(index=ES_ZINDEX, id=article.id):
        current_doc = es.get(index=ES_ZINDEX, id=article.id)
        doc_data = document_from_source(
            article, session, current_doc=current_doc["_source"]
        )
        doc["_op_type"] = "update"
        doc["_source"] = {"doc": doc_data}
    else:
        doc_data = document_from_source(article, session)
        doc["_op_type"] = "create"
        doc["_source"] = doc_data
    return doc


def index_in_elasticsearch(new_article, session):
    """
    # Saves the news article at ElasticSearch.
    # We recommend that everything is stored both in SQL and Elasticsearch
    # as ElasticSearch isn't persistent data
    """
    try:
        es = Elasticsearch(ES_CONN_STRING)
        doc = document_from_source(new_article, session)
        res = es.index(index=ES_ZINDEX, id=new_article.id, document=doc)

    except Exception as e:
        import traceback

        traceback.print_exc()


def remove_from_index(article):
    es = Elasticsearch(ES_CONN_STRING)
    if es.exists(index=ES_ZINDEX, id=article.id):
        print("Found in ES Index")
        es.delete(index=ES_ZINDEX, id=article.id)
        print("After deletion from the index.")
