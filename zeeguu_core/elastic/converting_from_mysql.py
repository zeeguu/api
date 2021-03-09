from zeeguu_core.model import Topic
from zeeguu_core.model.article import article_topic_map


def find_topics(article_id, session):
    article_topic = session.query(Topic).join(article_topic_map).filter(
        article_topic_map.c.article_id == article_id)
    topics = ""
    for t in article_topic:
        topics = topics + str(t.title) + " "

    return topics.rstrip()


def document_from_article(article, session):
    topics = find_topics(article.id, session)
    doc = {
        'title': article.title,
        'author': article.authors,
        'content': article.content,
        'summary': article.summary,
        'word_count': article.word_count,
        'published_time': article.published_time,
        'topics': topics,
        'language': article.language.name,
        'fk_difficulty': article.fk_difficulty
    }
    return doc
