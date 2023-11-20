import flask
from zeeguu.logging import log
from flask import request
from zeeguu.core.model.search import Search
from zeeguu.core.model.search_filter import SearchFilter
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.core.model.user_article import UserArticle

from zeeguu.core.content_recommender import article_search_for_user

from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from zeeguu.api.utils.json_result import json_result
from . import api

import zeeguu

db_session = zeeguu.core.model.db.session

SEARCH = "search"
SUBSCRIBE_SEARCH = "subscribe_search"
UNSUBSCRIBE_SEARCH = "unsubscribe_search"
SUBSCRIBED_SEARCHES = "subscribed_searches"
FILTER_SEARCH = "filter_search"
UNFILTER_SEARCH = "unfilter_search"
FILTERED_SEARCHES = "filtered_searches"


# ---------------------------------------------------------------------------
@api.route(f"/{SUBSCRIBE_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def subscribe_to_search(search_terms):
    """
    :param: search_terms -- the search terms to be subscribed to.
    Subscribe to a search with given search terms.

    :return: it returns the search as a dictionary. Like:
                id = unique id of the search;
                search_keywords = <unicode string>
             This is used to display it in the UI.

    """
    search = Search.find_or_create(db_session, search_terms)
    SearchSubscription.find_or_create(db_session, flask.g.user, search)

    return json_result(search.as_dictionary())


# ---------------------------------------------------------------------------
@api.route(f"/{UNSUBSCRIBE_SEARCH}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def unsubscribe_from_search():
    """
    A user can unsubscribe from the search with a given ID

    :return: OK / ERROR
    """

    search_id = int(request.form.get("search_id", ""))

    try:
        to_delete = SearchSubscription.with_search_id(search_id, flask.g.user)
        db_session.delete(to_delete)
        to_delete2 = Search.find_by_id(search_id)
        db_session.delete(to_delete2)
        db_session.commit()

    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        log(str(e))
        return "OOPS. SEARCH AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{SUBSCRIBED_SEARCHES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_subscribed_searches():
    """
    A user might be subscribed to multiple searches at once.
    This endpoint returns them as a list.

    :return: a json list with searches for which the user is registered;
     every search in this list is a dictionary with the following info:
                id = unique id of the search;
                search_keywords = <unicode string>
    """
    subscriptions = SearchSubscription.all_for_user(flask.g.user)
    searches_list = []

    for subs in subscriptions:
        try:
            searches_list.append(subs.search.as_dictionary())
        except Exception as e:
            log(str(e))
            from sentry_sdk import capture_exception

            capture_exception(e)

    return json_result(searches_list)


# ---------------------------------------------------------------------------
@api.route(f"/{FILTER_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def filter_search(search_terms):
    """
    Subscribe to the search filter with the given terms.
    :param: search_terms -- the search to be filtered.
    :return: the search as a dictionary
    """

    search = Search.find_or_create(db_session, search_terms)
    SearchFilter.find_or_create(db_session, flask.g.user, search)

    return json_result(search.as_dictionary())


# ---------------------------------------------------------------------------
@api.route(f"/{UNFILTER_SEARCH}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def unfilter_search():
    """
    A user can unsubscribe from the search with a given ID
    :return: OK / ERROR
    """

    search_id = int(request.form.get("search_id", ""))

    try:
        to_delete = SearchFilter.with_search_id(search_id, flask.g.user)
        db_session.delete(to_delete)
        to_delete = Search.find_by_id(search_id)
        db_session.delete(to_delete)
        db_session.commit()

    except Exception as e:
        log(str(e))
        from sentry_sdk import capture_exception

        capture_exception(e)
        return "OOPS. SEARCH AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{FILTERED_SEARCHES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_filtered_searches():
    """
    A user might be subscribed to multiple search filters at once.
    This endpoint returns them as a list.

    :return: a json list with searches for which the user is registered;
     every search in this list is a dictionary with the following info:
                id = unique id of the topic;
                search_keywords = <unicode string>
    """
    filters = SearchFilter.all_for_user(flask.g.user)
    filtered_searches = []

    for filt in filters:
        try:
            filtered_searches.append(filt.search.as_dictionary())
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            log(str(e))

    return json_result(filtered_searches)


# ---------------------------------------------------------------------------
@api.route(f"/{SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def search_for_search_terms(search_terms):
    """
    This endpoint is used for the standard search.
    It passes the search terms to the mysql_recommender function
    and returns the articles in a json format as a list.

    :param search_terms:
    :return: json article list for the search term

    """

    articles = article_search_for_user(flask.g.user, 20, search_terms)
    article_infos = [UserArticle.user_article_info(flask.g.user, a) for a in articles]

    return json_result(article_infos)
