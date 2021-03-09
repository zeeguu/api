import flask
import zeeguu_core
from flask import request
from zeeguu_core.model import RSSFeedRegistration, RSSFeed
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu_core.db.session

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
    if request.form.get("source_id", ""):
        feed_id = int(request.form.get("source_id", ""))
    else:
        feed_id = int(request.form.get("feed_id", ""))

    feed_object = RSSFeed.find_by_id(feed_id)
    RSSFeedRegistration.find_or_create(session, flask.g.user, feed_object)

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{STOP_FOLLOWING_FEED}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def stop_following_feed():
    """
    A user can stop following the feed with a given ID
    :return: OK / ERROR
    """

    feed_id = int(request.form.get("source_id", ""))

    try:
        to_delete = RSSFeedRegistration.with_feed_id(feed_id, flask.g.user)
        session.delete(to_delete)
        session.commit()
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
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
            from sentry_sdk import capture_exception

            capture_exception(e)
            zeeguu_core.log(str(e))

    return json_result(feed_list)


# ---------------------------------------------------------------------------
@api.route(f"/{INTERESTING_FEEDS}/<language_code>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_interesting_feeds_for_language_code(language_code):
    """
    Get a list of feeds for the given language

    :return:
    """
    feed_data = []
    for feed in RSSFeed.find_for_language_id(language_code):
        feed_data.append(feed.as_dictionary())
    return json_result(feed_data)


# ---------------------------------------------------------------------------
@api.route(f"/{RECOMMENDED_FEEDS}/<language_code>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_non_subscribed_feeds(language_code):
    """
    Get a list of feeds for the given language

    :return:
    """
    feeds = RSSFeedRegistration.non_subscribed_feeds(flask.g.user, language_code)
    feed_data = [feed.as_dictionary() for feed in feeds]
    return json_result(feed_data)
