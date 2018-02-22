from datetime import datetime

from zeeguu import log
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

    log(f'event is: {event}')
    if "UMR - OPEN ARTICLE" in event:
        article_opened(session, value, user)
    elif "UMR - LIKE ARTICLE" in event:
        article_liked(session, value, user, True)
    elif "UMR - UNLIKE ARTICLE" in event:
        article_liked(session, value, user, False)


def article_liked(session, value, user, like_value):
    # the url that comes from zeeguu event logger
    # might be the zeeguu url: which is of the form
    # https://www.zeeguu.unibe.ch/read/article?articleLanguage=de&articleURL=https://www.nzz.ch/wissenschaft/neandertaler-waren-kuenstler-ld.1358862
    # thus we extract only the last part
    url = value.split('articleURL=')[-1]

    article = Article.find_or_create(session, url)
    ua = UserArticle.find_or_create(session, user, article)
    ua.liked = like_value
    session.add(ua)
    session.commit()
    log(f"created new {ua}")


def article_opened(session, value, user):
    # the url that comes from zeeguu event logger
    # might be the zeeguu url: which is of the form
    # https://www.zeeguu.unibe.ch/read/article?articleLanguage=de&articleURL=https://www.nzz.ch/wissenschaft/neandertaler-waren-kuenstler-ld.1358862
    # thus we extract only the last part
    url = value.split('articleURL=')[-1]

    article = Article.find_or_create(session, url)
    ua = UserArticle.find_or_create(session, user, article)
    ua.opened = datetime.now()
    session.add(ua)
    session.commit()
    log(f"created new {ua}")
