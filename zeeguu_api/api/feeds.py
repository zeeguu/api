import flask
import zeeguu
from flask import request
from zeeguu.model import RSSFeedRegistration, RSSFeed

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session

START_FOLLOWING_FEED = "start_following_feed"
STOP_FOLLOWING_FEED = "stop_following_feed"
FOLLOWED_FEEDS = "followed_feeds"
INTERESTING_FEEDS = "interesting_feeds"
RECOMMENDED_FEEDS = "recommended_feeds"


# ---------------------------------------------------------------------------
@api.route(f"/{START_FOLLOWING_FEED}", methods=("POST",))
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
    RSSFeedRegistration.find_or_create(session, flask.g.user, feed_object)

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{STOP_FOLLOWING_FEED}/<feed_id>", methods=("GET",))
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
@api.route(f"/{FOLLOWED_FEEDS}", methods=("GET",))
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
        except Exception as e:
            zeeguu.log(str(e))

    return json_result(feed_list)


# ---------------------------------------------------------------------------
@api.route(f"/{INTERESTING_FEEDS}/<language_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_interesting_feeds_for_language_id(language_id):
    """
    Get a list of feeds for the given language

    :return:
    """
    feed_data = []
    for feed in RSSFeed.find_for_language_id(language_id):
        feed_data.append(feed.as_dictionary())
    return json_result(feed_data)


# ---------------------------------------------------------------------------
@api.route(f"/{RECOMMENDED_FEEDS}/<language_id>", methods=("GET",))
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

    all_available_for_language = RSSFeed.find_for_language_id(language_id)
    print (f"language id is: {language_id}")
    for feed in all_available_for_language:
        if not (feed in already_registered):
            feed_data.append(feed.as_dictionary())

    return json_result(feed_data)
