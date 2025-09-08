import flask
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.logging import log
from flask import request
from zeeguu.core.model.search import Search
from zeeguu.core.model.search_filter import SearchFilter
from zeeguu.core.model.search_subscription import SearchSubscription
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model import User

from zeeguu.core.content_recommender import (
    article_and_video_search_for_user,
    get_user_info_from_content_recommendations,
)

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api

import zeeguu

db_session = zeeguu.core.model.db.session

SEARCH = "search"
LATEST_SEARCH = "latest_search"
SUBSCRIBE_SEARCH = "subscribe_search"
UNSUBSCRIBE_SEARCH = "unsubscribe_search"
SUBSCRIBED_SEARCHES = "subscribed_searches"
FILTER_SEARCH = "filter_search"
UNFILTER_SEARCH = "unfilter_search"
FILTERED_SEARCHES = "filtered_searches"
SUBSCRIBE_TO_EMAIL_SEARCH = "subscribe_to_email_search"
UNSUBSCRIBE_FROM_EMAIL_SEARCH = "unsubscribe_from_email_search"


def get_total_subscriptions_exclusions_for_search(search_id):
    total_excluding = SearchFilter.get_number_of_users_excluding(search_id)
    total_subscribers = SearchSubscription.get_number_of_subscribers(search_id)
    return total_excluding + total_subscribers


# ---------------------------------------------------------------------------
@api.route(f"/{SUBSCRIBE_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def subscribe_to_search(search_terms):
    """
    :param: search_terms -- the search terms to be subscribed to.
    Subscribe to a search with given search terms.

    :return: it returns the search as a dictionary. Like:
                id = unique id of the search;
                search_keywords = <unicode string>
             This is used to display it in the UI.

    """
    user = User.find_by_id(flask.g.user_id)
    search = Search.find_or_create(db_session, search_terms, user.learned_language_id)
    receive_email = False
    subscription = SearchSubscription.find_or_create(
        db_session, user, search, receive_email
    )

    return json_result(subscription.as_dictionary())


# ---------------------------------------------------------------------------
@api.route(f"/{UNSUBSCRIBE_SEARCH}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def unsubscribe_from_search():
    """
    A user can unsubscribe from the search with a given ID

    :return: OK / ERROR
    """

    search_id = int(request.form.get("search_id", ""))
    user = User.find_by_id(flask.g.user_id)
    try:
        to_delete = SearchSubscription.with_search_id(search_id, user)
        db_session.delete(to_delete)

        search = Search.find_by_id(search_id)
        users_following_topic = get_total_subscriptions_exclusions_for_search(search_id)
        if users_following_topic == 0:
            db_session.delete(search)
        db_session.commit()

    except Exception as e:
        from zeeguu.logging import print_and_log_to_sentry

        print_and_log_to_sentry(e)
        log(str(e))
        return "OOPS. SEARCH AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{SUBSCRIBED_SEARCHES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_subscribed_searches():
    """
    A user might be subscribed to multiple searches at once.
    This endpoint returns them as a list.

    :return: a json list with searches for which the user is registered;
     every search in this list is a dictionary with the following info:
                id = unique id of the search;
                search_keywords = <unicode string>
    """
    user = User.find_by_id(flask.g.user_id)
    subscriptions = SearchSubscription.all_for_user(user)
    searches_list = []

    for subs in subscriptions:
        try:
            searches_list.append(subs.as_dictionary())
        except Exception as e:
            from zeeguu.logging import print_and_log_to_sentry

            print_and_log_to_sentry(e)

    return json_result(searches_list)


# ---------------------------------------------------------------------------
@api.route(f"/{FILTER_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def filter_search(search_terms):
    """
    Subscribe to the search filter with the given terms.
    :param: search_terms -- the search to be filtered.
    :return: the search as a dictionary
    """
    user = User.find_by_id(flask.g.user_id)
    search = Search.find_or_create(db_session, search_terms, user.learned_language_id)
    SearchFilter.find_or_create(db_session, user, search)

    return json_result(search.as_dictionary())


# ---------------------------------------------------------------------------
@api.route(f"/{UNFILTER_SEARCH}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def unfilter_search():
    """
    A user can unsubscribe from the search with a given ID
    :return: OK / ERROR
    """

    search_id = int(request.form.get("search_id", ""))
    user = User.find_by_id(flask.g.user_id)
    try:
        to_delete = SearchFilter.with_search_id(search_id, user)
        db_session.delete(to_delete)
        users_following_topic = get_total_subscriptions_exclusions_for_search(search_id)
        if users_following_topic == 0:
            search = Search.find_by_id(search_id)
            db_session.delete(search)
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
@requires_session
def get_filtered_searches():
    """
    A user might be subscribed to multiple search filters at once.
    This endpoint returns them as a list.

    :return: a json list with searches for which the user is registered;
     every search in this list is a dictionary with the following info:
                id = unique id of the topic;
                search_keywords = <unicode string>
    """
    user = User.find_by_id(flask.g.user_id)
    filters = SearchFilter.all_for_user(user)
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
@api.route(f"/{SEARCH}/<search_terms>", methods=("GET", "POST"))
@api.route(f"/{SEARCH}/<search_terms>/<int:page>", methods=("GET", "POST"))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def search_for_search_terms(search_terms, page: int = 0):
    """
    This endpoint is used for the standard search. It prioritizes
    relevancy and user difficulty by default. The user can toggle
    if they would like to prioritize the difficulty and recency
    in the UI.

    It passes the search terms to the mysql_recommender function
    and returns the articles in a json format as a list.

    :param search_terms:
    :return: json article list for the search term

    """
    # Default params
    use_published_priority = False
    use_readability_priority = True

    if request.method == "POST":
        use_published_priority = (
            request.form.get("use_publish_priority", "false") == "true"
        )
        use_readability_priority = (
            request.form.get("use_readability_priority", "true") == "true"
        )

    user = User.find_by_id(flask.g.user_id)
    results = article_and_video_search_for_user(
        user,
        20,
        search_terms,
        page=page,
        use_published_priority=use_published_priority,
        use_readability_priority=use_readability_priority,
    )
    
    # Filter out hidden articles
    from zeeguu.core.model import UserArticle
    filtered_results = UserArticle.filter_hidden_content(user, results)

    return json_result(get_user_info_from_content_recommendations(user, filtered_results))


# ---------------------------------------------------------------------------
@api.route(f"/{LATEST_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def search_for_latest_search_terms(search_terms):
    """
    This endpoint is used for the preview search and sending notification
    emails.
    The call prioritizes the recency of articles paried with the difficulty.
    It has a reduced count as we are only checking if there are new relevant
    documents for those keywords.

    :param search_terms:
    :return: json article list for the search term

    """

    user = User.find_by_id(flask.g.user_id)
    articles = article_and_video_search_for_user(
        user,
        3,
        search_terms,
        page=0,
        use_published_priority=True,
        use_readability_priority=True,
        score_threshold=2,
    )
    
    # Filter out hidden articles  
    filtered_articles = UserArticle.filter_hidden_content(user, articles)
    
    article_infos = [UserArticle.user_article_info(user, UserArticle.select_appropriate_article_for_user(user, a)) for a in filtered_articles]

    return json_result(article_infos)


@api.route(f"/{SUBSCRIBE_TO_EMAIL_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def subscribe_to_email_search(search_terms):
    """
    A user can subscribe to email updates about a search
    """
    user = User.find_by_id(flask.g.user_id)
    search = Search.find(search_terms, user.learned_language_id)
    receive_email = True
    subscription = SearchSubscription.update_receive_email(
        db_session, user, search, receive_email
    )

    return json_result(subscription.as_dictionary())


@api.route(f"/{UNSUBSCRIBE_FROM_EMAIL_SEARCH}/<search_terms>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def unsubscribe_from_email_search(search_terms):
    """
    A user can unsubscribe to email updates about a search
    """
    user = User.find_by_id(flask.g.user_id)
    search = Search.find(search_terms, user.learned_language_id)

    receive_email = False
    subscription = SearchSubscription.update_receive_email(
        db_session, user, search, receive_email
    )

    return json_result(subscription.as_dictionary())
