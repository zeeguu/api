import flask
from zeeguu.logging import log
from flask import request
from zeeguu.core.model import (
    Topic,
    TopicSubscription,
    TopicFilter,
    LocalizedTopic,
    Language,
)

from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from zeeguu.api.utils.json_result import json_result
from . import api

import zeeguu

db_session = zeeguu.core.model.db.session

SUBSCRIBE_TOPIC = "subscribe_topic"
UNSUBSCRIBE_TOPIC = "unsubscribe_topic"
SUBSCRIBED_TOPICS = "subscribed_topics"
FILTER_TOPIC = "filter_topic"
UNFILTER_TOPIC = "unfilter_topic"
FILTERED_TOPICS = "filtered_topics"


# ---------------------------------------------------------------------------
@api.route(f"/{SUBSCRIBE_TOPIC}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def subscribe_to_topic_with_id():
    """
    :param: topic_id -- the id of the topic to be subscribed to.
    Subscribe to the topic with the given id

    :return: "OK" in case of success
    """

    topic_id = int(request.form.get("topic_id", ""))

    topic_object = Topic.find_by_id(topic_id)
    TopicSubscription.find_or_create(db_session, flask.g.user, topic_object)

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{UNSUBSCRIBE_TOPIC}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def unsubscribe_from_topic():
    """
    A user can unsubscribe from the topic with a given ID

    :return: "OK" in case of success
    """

    topic_id = int(request.form.get("topic_id", ""))

    try:
        to_delete = TopicSubscription.with_topic_id(topic_id, flask.g.user)
        db_session.delete(to_delete)
        db_session.commit()
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        return "OOPS. FEED AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{SUBSCRIBED_TOPICS}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_subscribed_topics():
    """
    A user might be subscribed to multiple topics at once.
    This endpoint returns them as a list.

    :return: a json list with feeds for which the user is registered;
     every feed in this list is a dictionary with the following info:
                id = unique id of the topic;
                title = <unicode string>
    """
    subscriptions = TopicSubscription.all_for_user(flask.g.user)
    topic_list = []
    for sub in subscriptions:
        try:
            topic_list.append(sub.topic.as_dictionary())
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            log(str(e))

    return json_result(topic_list)


# ---------------------------------------------------------------------------
@api.route("/available_topics", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_available_topics():
    """
    Get a list of interesting topics for the given language.
    Interesting topics are for now defined as:
        - There are articles with that topic in the language
        - The topic is not followed yet
        - The topic is not in the filters list

    :return:
    """
    topic_data = []
    already_filtered = [each.topic for each in TopicFilter.all_for_user(flask.g.user)]
    already_subscribed = [
        each.topic for each in TopicSubscription.all_for_user(flask.g.user)
    ]

    reading_languages = Language.all_reading_for_user(flask.g.user)

    loc_topics = []
    for each in reading_languages:
        loc_topics.extend(LocalizedTopic.all_for_language(each))

    topics = [each.topic for each in loc_topics]

    for topic in topics:
        if (topic not in already_filtered) and (topic not in already_subscribed):
            topic_data.append(topic.as_dictionary())
    return json_result(topic_data)


# ---------------------------------------------------------------------------
@api.route(f"/{FILTER_TOPIC}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def subscribe_to_filter_with_id():
    """
    :param: filter_id -- the id of the filter to be subscribed to.
    Subscribe to the filter with the given id

    :return: "OK" in case of success
    """

    filter_id = int(request.form.get("filter_id", ""))

    filter_object = Topic.find_by_id(filter_id)
    TopicFilter.find_or_create(db_session, flask.g.user, filter_object)

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{UNFILTER_TOPIC}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def unsubscribe_from_filter():
    """
    A user can unsubscribe from the filter with a given ID
    :return: OK / ERROR
    """

    filter_id = int(request.form.get("topic_id", ""))

    try:
        to_delete = TopicFilter.with_topic_id(filter_id, flask.g.user)
        db_session.delete(to_delete)
        db_session.commit()
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        return "OOPS. FILTER AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{FILTERED_TOPICS}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_subscribed_filters():
    """
    A user might be subscribed to multiple filters at once.
    This endpoint returns them as a list.

    :return: a json list with filters for which the user is registered;
     every filter in this list is a dictionary with the following info:
                id = unique id of the topic;
                title = <unicode string>
    """
    filters = TopicFilter.all_for_user(flask.g.user)
    filter_list = []
    for fil in filters:
        try:
            filter_list.append(fil.topic.as_dictionary())
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            log(str(e))

    return json_result(filter_list)


@api.route(f"/cache_articles/<code>", methods=("GET",))
def cache_articles(code):
    if code != zeeguu.core.app.config.get("PRIVATE_API_CODE"):
        return "Nope"

    from zeeguu.core.model import Topic, Language

    for each in Topic.get_all_topics():
        each.all_articles()

    for each in Language.available_languages():
        each.get_articles()

    return "OK"
