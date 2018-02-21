import json

import feedparser
import flask
import zeeguu
from flask import request
from zeeguu.model import RSSFeedRegistration, RSSFeed, Language, Url

from .utils.route_wrappers import cross_domain, with_session
from .utils.feedparser_extensions import list_of_feeds_at_url, two_letter_language_code
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session


# ---------------------------------------------------------------------------
@api.route("/get_feeds_being_followed", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_feeds_being_followed():
    """
    A user might be following multiple feeds at once.
    This endpoint returns them as a list.

    :return: a json list with feeds for which the user is registered;
     every feed in this list is a dictionary with the following info:
                id = unique id of the feed; uniquely identifies feed in other endpoints
                title = <unicode string>
                url = ...
                language = ...
                image_url = ...
    """
    registrations = RSSFeedRegistration.feeds_for_user(flask.g.user)
    feed_list = []
    for reg in registrations:
        try:
            feed_list.append(reg.rss_feed.as_dictionary())
            # print (f"added reg with id: {reg.id}")
        except Exception as e:
            # print (f"failed reg with id: {reg.id}")
            print(str(e))

    return json_result(feed_list)


# ---------------------------------------------------------------------------
@api.route("/start_following_feed_with_id", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def start_following_feed_with_id():
    """
    :param: feed_id -- the id of the feed to be followed.
    Start following the feed with the given id

    :return: "OK" in case of success
    """

    feed_id = int(request.form.get('feed_id', ''))

    feed_object = RSSFeed.find_by_id(feed_id)
    feed_registration = RSSFeedRegistration.find_or_create(session, flask.g.user, feed_object)

    return "OK"


# ---------------------------------------------------------------------------
@api.route("/stop_following_feed/<feed_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def stop_following_feed(feed_id):
    """
    A user can stop following the feed with a given ID
    :return: OK / ERROR
    """

    try:
        to_delete = RSSFeedRegistration.with_feed_id(feed_id, flask.g.user)
        session.delete(to_delete)
        session.commit()
    except Exception as e:
        return "OOPS. FEED AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


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

        Retrieve :param _count articles which are distributed
        over all the feeds to which the learner is registered to.

    :param _count:

    :return: json list of Article.article_info() data

    """
    count = int(_count)

    all_user_registrations = RSSFeedRegistration.feeds_for_user(flask.g.user)
    per_feed_count = int(count / len(all_user_registrations)) + 1

    all_articles = []
    for registration in all_user_registrations:
        feed = registration.rss_feed
        zeeguu.log(f'Getting articles for {feed}')
        new_articles = feed.get_articles(flask.g.user, limit=per_feed_count, most_recent_first=True)
        all_articles.extend(new_articles)
        zeeguu.log(f'Added articles for {feed}')

    zeeguu.log('Sorting articles...')
    all_articles.sort(key=lambda each: each.published_time, reverse=True)
    zeeguu.log('Sorted articles')

    return json_result([each.article_info() for each in all_articles[:count]])


# ---------------------------------------------------------------------------
@api.route("/interesting_feeds/<language_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_interesting_feeds_for_language_id(language_id):
    """
    Get a list of feeds for the given language

    :return:
    """
    feed_data = []
    print("trying to get feeds for {0}".format(language_id))
    for feed in RSSFeed.find_for_language_id(language_id):
        feed_data.append(feed.as_dictionary())
    return json_result(feed_data)


# ---------------------------------------------------------------------------
@api.route("/non_subscribed_feeds/<language_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_non_subscribed_feeds(language_id):
    """
    Get a list of feeds for the given language

    :return:
    """
    feed_data = []
    already_registered = [each.rss_feed for each in RSSFeedRegistration.feeds_for_user(flask.g.user)]

    # print("trying to get feeds for {0} and {1}".format(language_id, flask.g.user.name))
    all_available_for_language = RSSFeed.find_for_language_id(language_id)
    for feed in all_available_for_language:
        if not feed in already_registered:
            feed_data.append(feed.as_dictionary())

    return json_result(feed_data)
