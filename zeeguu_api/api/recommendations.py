import flask
import zeeguu
from zeeguu.content_recommender.mixed_recommender import article_recommendations_for_user
from zeeguu.model import RSSFeedRegistration, RSSFeed

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session


# ---------------------------------------------------------------------------
@api.route("/get_feed_items_with_metrics/<feed_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_feed_items_with_metrics(feed_id):
    """
    Get a list of feed items for a given feed ID

    :return: json list of dicts, with the following info:
                    title   = <unicode string>
                    url     = <unicode string>
                    content = <list> e.g.:
                        [{u'base': u'http://www.spiegel.de/schlagzeilen/index.rss',
                         u'type': u'text/html', u'language': None, u'value': u'\xdcberwachungskameras, die bei Aldi verkauft wurden, haben offenbar ein Sicherheitsproblem: Hat man kein Passwort festgelegt, \xfcbertragen sie ihre Aufnahmen ungesch\xfctzt ins Netz - und verraten au\xdferdem WLAN- und E-Mail-Passw\xf6rter.'}]
                    summary = <unicode string>
                    published= <unicode string> e.g.
                        'Fri, 15 Jan 2016 15:26:51 +0100'
    """
    feed = RSSFeed.query.get(feed_id)
    articles = feed.get_articles(flask.g.user, 20, most_recent_first=True)
    return json_result([article.article_info() for article in articles])


# ---------------------------------------------------------------------------
@api.route("/get_recommended_articles", methods=("GET",))
@api.route("/get_recommended_articles/<_count>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def top_recommended_articles(_count: str = 10):
    """

        Retrieve :param _count articles which are equally distributed
        over all the feeds to which the learner is registered to.

    :param _count:

    :return: json list of Article.article_info() data

    """
    count = int(_count)

    return json_result(article_recommendations_for_user(flask.g.user, count))
