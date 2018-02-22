import datetime
from zeeguu.model import Article, UserArticle


def distill_article_interactions(session, user, data):
    """

        extracts info from user_activity_data

    :param session:
    :param event:
    :param value:
    :param user:
    """

    time = data['time']
    event = data['event']
    value = data['value']
    extra_data = data['extra_data']

    if "UMR - OPEN ARTICLE" in event:
        article_opened(session, value, user)
    # elif "UMR - LIKE ARTICLE" in event:
    #     article_like()


def article_opened(session, url, user):
    article = Article.find_or_create(session, url)
    UserArticle.find_or_create(session, user, article, opened=datetime.now())
