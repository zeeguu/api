import json

import flask
from zeeguu.api.endpoints.feature_toggles import features_for_user
import zeeguu.core
from zeeguu.core.model import User

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api
from ...core.model import UserActivityData, UserArticle, Article
from zeeguu.core.model.feedback_component import FeedbackComponent
from zeeguu.core.model.user_feedback import UserFeedback
from zeeguu.core.model.url import Url


@api.route("/learned_language", methods=["GET"])
@cross_domain
@requires_session
def learned_language():
    """
    Each endpoint is defined by a function definition
    of the same form as this one.

    The important information for understanding the
    endpoint is in the annotations before the function
    and in the comment immediately after the function
    name.

    Two types of annotations are important:

     @endpoints.route gives you the endpoint name together
        with the expectd HTTP method
        it is normally appended to the API_URL (https://www.zeeguu.unibe.ch/)

     @with_session means that you must submit a session
        argument together wit your API request
        e.g. API_URL/learned_language?session=123141516
    """
    user = User.find_by_id(flask.g.user_id)
    return user.learned_language.code


@api.route("/learned_language/<language_code>", methods=["POST"])
@cross_domain
@requires_session
def learned_language_set(language_code):
    """
    Set the learned language
    :param language_code: one of the ISO language codes
    :return: "OK" for success
    """
    user = User.find_by_id(flask.g.user_id)
    user.set_learned_language(language_code, session=zeeguu.core.model.db.session)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/native_language", methods=["GET"])
@cross_domain
@requires_session
def native_language():
    user = User.find_by_id(flask.g.user_id)
    return user.native_language.code


@api.route("/native_language/<language_code>", methods=["POST"])
@cross_domain
@requires_session
def native_language_set(language_code):
    """
    :param language_code:
    :return: OK for success
    """
    user = User.find_by_id(flask.g.user_id)
    user.set_native_language(language_code)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/learned_and_native_language", methods=["GET"])
@cross_domain
@requires_session
def learned_and_native_language():
    """
    Get both the native and the learned language
    for the user in session
    :return:
    """
    user = User.find_by_id(flask.g.user_id)
    res = dict(native=user.native_language_id, learned=user.learned_language_id)
    return json_result(res)


@api.route("/get_unfinished_user_reading_sessions", methods=("GET",))
@api.route(
    "/get_unfinished_user_reading_sessions/<int:total_sessions>", methods=("GET",)
)
@cross_domain
@requires_session
def get_user_unfinished_reading_sessions(total_sessions: int = 1):
    """
    Retrieves the last uncompleted sessions based on the SCROLL events of the user.

    """
    user = User.find_by_id(flask.g.user_id)
    last_sessions = (
        UserActivityData.get_articles_with_reading_percentages_for_user_in_date_range(
            user, limit=total_sessions
        )
    )
    list_result = []
    for s in last_sessions:
        art_id, date_read, viewport_settings, last_reading_point = s
        if last_reading_point < 0.9 and last_reading_point > 0:
            scrollHeight = viewport_settings["scrollHeight"]
            clientHeight = viewport_settings["clientHeight"]
            bottomRowHeight = viewport_settings["bottomRowHeight"]
            art = Article.find_by_id(art_id)
            art_info = UserArticle.user_article_info(user, UserArticle.select_appropriate_article_for_user(user, art))
            # We might use these for a more complex calculation of where to lead the user
            # art_info["total_scroll_height"] = (scrollHeight - clientHeight - bottomRowHeight)
            # art_info["pixel_to_scroll_to"] = (scrollHeight - clientHeight - bottomRowHeight) * (last_reading_point)
            art_info["time_last_read"] = date_read
            # Give a tolerance based on the viewPort to scroll a bit before the maximum point.
            tolerance = clientHeight / ((scrollHeight - bottomRowHeight)) / 4
            last_reading_percentage = last_reading_point - tolerance
            if last_reading_percentage <= 0:
                continue
            art_info["last_reading_percentage"] = last_reading_percentage
            list_result.append(art_info)

    return json_result(list_result)


@api.route("/get_user_details", methods=("GET",))
@cross_domain
@requires_session
def get_user_details():
    """
    after the login, this information might be useful to be displayed
    by an app
    :param lang_code:
    :return:
    """
    user = User.find_by_id(flask.g.user_id)
    details_dict = user.details_as_dictionary()
    details_dict["features"] = features_for_user(user)

    return json_result(details_dict)


@api.route("/user_settings", methods=["POST"])
@cross_domain
@requires_session
def user_settings():
    """
    :return: OK for success
    """

    data = flask.request.form
    user = User.find_by_id(flask.g.user_id)

    submitted_name = data.get("name", None)
    if submitted_name:
        user.name = submitted_name

    submitted_native_language_code = data.get("native_language", None)
    if submitted_native_language_code:
        user.set_native_language(submitted_native_language_code)

    cefr_level = data.get("cefr_level", None)
    submitted_learned_language_code = data.get("learned_language", None)

    if submitted_learned_language_code:
        user.set_learned_language(
            submitted_learned_language_code, cefr_level, zeeguu.core.model.db.session
        )

    submitted_email = data.get("email", None)
    if submitted_email:
        user.email = submitted_email

    zeeguu.core.model.db.session.add(user)
    zeeguu.core.model.db.session.commit()
    return "OK"


@api.route("/send_feedback", methods=["POST"])
@cross_domain
@requires_session
def send_feedback():
    session = zeeguu.core.model.db.session
    message = flask.request.form.get("message", "")
    url = flask.request.form.get("currentUrl", None)
    
    # Get component name from frontend
    component_name = flask.request.form.get("feedbackComponentName", "")
    
    from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

    user = User.find_by_id(flask.g.user_id)
    
    # Use component name or default
    feedback_component = FeedbackComponent.find_or_create(session, component_name or "General Feedback")
    
    if url is not None:
        url = Url.find_or_create(session, url)

    user_feedback = UserFeedback.create(session, user, feedback_component, message, url)
    session.commit()
    ZeeguuMailer.send_feedback(
        "Feedback",
        feedback_component.component_type,
        message,
        user,
        str(url) if url else None,
    )
    return "OK"


@api.route("/leave_cohort/<cohort_id>", methods=["GET"])
@cross_domain
@requires_session
def leave_cohort(cohort_id):
    from zeeguu.core.model.db import db

    """
    set the native language of the user in session
    :return: OK for success
    """
    try:
        user = User.find_by_id(flask.g.user_id)
        user.remove_from_cohort(cohort_id, db.session)
        return "OK"
    except Exception as e:
        print(e)
        return "FAIL"
