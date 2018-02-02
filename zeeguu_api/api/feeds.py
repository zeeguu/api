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
@api.route("/get_feeds_at_url", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_feeds_at_url():
    """
    :return: a list of feeds that can be found at the given URL
    Empty list if soemething
    """
    domain = request.form.get('url', '')
    return json_result(list_of_feeds_at_url(domain))


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
@api.route("/start_following_feeds", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def start_following_feeds():
    """
    :param: feeds (POST param) -- json list with urls for the feeds to be followed

    Starts following all the feeds in the feeds param.
    To follow a single feed provide a list with one element.

    :return: "OK" in case of success
    """

    list_of_feed_urls = json.loads(request.form.get('feeds', ''))

    for url_string in list_of_feed_urls:
        feed = feedparser.parse(url_string).feed

        feed_image_url_string = ""
        if "image" in feed:
            feed_image_url_string = feed.image["href"]

        lan = None
        if "language" in feed:
            lan = Language.find(two_letter_language_code(feed))

        url = Url.find_or_create(session, url_string)

        feed_object = RSSFeed.find_by_url(url)
        if not feed_object:
            feed_image_url = Url.find_or_create(session, feed_image_url_string)
            title = url
            if "title" in feed:
                title = feed.title
            feed_object = RSSFeed.find_or_create(session, url, title, feed.description, feed_image_url, lan)

        RSSFeedRegistration.find_or_create(session, flask.g.user, feed_object)

    return "OK"


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
    registration = RSSFeedRegistration.with_feed_id(feed_id, flask.g.user)
    return json_result(registration.rss_feed.feed_items_with_metrics(flask.g.user, 40))


# ---------------------------------------------------------------------------
@api.route("/get_top_recommended_articles/<_count>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def top_recommended_articles(_count: str):
    """

        Get a list of :param count articles that are
        recommended reading for this user

        This only works if the user has some news sources
        that he is registered to. 

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
    count = int(_count)
    registration = RSSFeedRegistration.feeds_for_user(flask.g.user)[0]

    all_articles = registration.rss_feed.feed_items()

    return json_result(all_articles[:count])


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


# ---------------------------------------------------------------------------
@api.route("/add_new_feed", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def add_new_feed():
    """

        Add a new feed to the DB.
        More of an internal tool.
        Useful when /start_following_feeds fails due to badly
        formed feeds that can't be parsed by feedparser.

    :param: feed_info is a dictionary which contains:
      - image
      - language
      - url
      - title
      - description

    :return: the id of the newly added feed
    """

    feed_info = json.loads(request.form.get('feed_info', ''))

    image_url = feed_info["image"]
    language = Language.find(feed_info["language"])
    url_string = feed_info["url"]
    title = feed_info["title"]
    description = feed_info["description"]

    url = Url.find_or_create(session, url_string)

    feed_image_url = Url.find_or_create(session, image_url)

    feed_object = RSSFeed.find_or_create(session, url, title, description, feed_image_url, language)

    return json.dumps(feed_object.id)


# ------------------------------------------------------------------------
#  DEPRECATED APIs
# ------------------------------------------------------------------------


@api.route("/start_following_feed", methods=("POST",))
@cross_domain
@with_session
def start_following_feed():
    """
    DEPRECATED!
     Use instead /add_new_feed followed by start_following_feed_with_id instead

    Start following a feed for which the client provides all the
    metadata. This is useful for the cases where badly formed
    feeds can't be parsed by feedparser.
    For

    :return:
    """

    feed_info = json.loads(request.form.get('feed_info'))

    image_url = feed_info["image"]
    language = Language.find(feed_info["language"])
    url_string = feed_info["url"]
    title = feed_info["title"]
    description = feed_info["description"]

    url = Url.find_or_create(session, url_string)

    feed_image_url = Url.find_or_create(session, image_url)

    feed_object = RSSFeed.find_or_create(session, url, title, description, feed_image_url, language)
    RSSFeedRegistration.find_or_create(session, flask.g.user, feed_object)

    return "OK"

# # ---------------------------------------------------------------------------
# @api.route("/get_feed_items/<feed_id>", methods=("GET",))
# # ---------------------------------------------------------------------------
# @cross_domain
# @with_session
# def get_feed_items_for(feed_id):
#     """
#     Get a list of feed items for a given feed ID
#
#     :return: json list of dicts, with the following info:
#                     title   = <unicode string>
#                     url     = <unicode string>
#                     content = <list> e.g.:
#                         [{u'base': u'http://www.spiegel.de/schlagzeilen/index.rss',
#                          u'type': u'text/html', u'language': None, u'value': u'\xdcberwachungskameras, die bei Aldi verkauft wurden, haben offenbar ein Sicherheitsproblem: Hat man kein Passwort festgelegt, \xfcbertragen sie ihre Aufnahmen ungesch\xfctzt ins Netz - und verraten au\xdferdem WLAN- und E-Mail-Passw\xf6rter.'}]
#                     summary = <unicode string>
#                     published= <unicode string> e.g.
#                         'Fri, 15 Jan 2016 15:26:51 +0100'
#     """
#     registration = RSSFeedRegistration.with_feed_id(feed_id, flask.g.user)
#     return json_result(registration.rss_feed.feed_items())
