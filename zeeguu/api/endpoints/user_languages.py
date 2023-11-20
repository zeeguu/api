import flask
import zeeguu.core
from flask import request
from zeeguu.core.model.language import Language
from zeeguu.core.model.user_language import UserLanguage


from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from zeeguu.api.utils.json_result import json_result
from . import api

db_session = zeeguu.core.model.db.session

USER_LANGUAGES = "user_languages"
MODIFY_USER_LANGUAGE = "user_languages/modify"
DELETE_USER_LANGUAGE = "user_languages/delete"
INTERESTING_LANGUAGES_FOR_READING = "user_languages/interesting_for_reading"
READING_LANGUAGES = "user_languages/reading"


# ---------------------------------------------------------------------------
@api.route(f"/{MODIFY_USER_LANGUAGE}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def modify_user_language():
    """
    This endpoint is for modifying a user language.
    It tries to find the user_language, and otherwise create it.
    It then sets all the parameters given.

    :return: "OK" in case of success
    """
    language_code = request.form.get("language_id", "")
    try:
        language_reading = int(request.form.get("language_reading", ""))
    except:
        language_reading = None
    try:
        language_exercises = int(request.form.get("language_exercises", ""))
    except:
        language_exercises = None
    try:
        language_level = int(request.form.get("language_level", ""))
    except:
        language_level = None

    language_object = Language.find(language_code)
    user_language = UserLanguage.find_or_create(
        db_session, flask.g.user, language_object
    )
    if language_reading is not None:
        user_language.reading_news = language_reading
    if language_exercises is not None:
        user_language.doing_exercises = language_exercises
    if language_level is not None:
        user_language.cefr_level = language_level
    db_session.add(user_language)
    db_session.commit()

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{DELETE_USER_LANGUAGE}/<language_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def delete_user_language(language_id):
    """
    A user can delete a language with a given ID.
    With this endpoint the full user language with all the data is deleted.
    At the moment not used but might be useful.

    :return: "OK" in case of success
    """

    try:
        to_delete = UserLanguage.with_language_id(language_id, flask.g.user)
        db_session.delete(to_delete)
        db_session.commit()
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        return "OOPS. SEARCH AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{USER_LANGUAGES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_user_languages():
    """
    A user might have multiple user languages, which can be for reading
    and/or doing exercises.

    :return: a json list with languages for which the user is registered;
     every language in this list is a dictionary with the following info:
                id = unique id of the language;
                language = <unicode string>
    """
    all_user_languages = []
    user_languages = UserLanguage.all_for_user(flask.g.user)
    for lan in user_languages:
        all_user_languages.append(lan.as_dictionary())
    return json_result(all_user_languages)


# ---------------------------------------------------------------------------
@api.route(f"/{READING_LANGUAGES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_reading_languages():
    """
    A user might be subscribed to multiple languages at once.
    This endpoint returns them as a list.

    :return: a json list with languages for which the user is registered;
     every language in this list is a dictionary with the following info:
                id = unique id of the language;
                language = <unicode string>
    """
    all_user_languages = []
    reading_languages = Language.all_reading_for_user(flask.g.user)
    for lan in reading_languages:
        all_user_languages.append(lan.as_dictionary())
    return json_result(all_user_languages)


# ---------------------------------------------------------------------------
@api.route(f"/{INTERESTING_LANGUAGES_FOR_READING}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_interesting_reading_languages():
    """
    'Interesting languages' are defined as languages the user
    isn't subscribed to already and thus might subscribe to.

    :return: a json list with languages the user isn't reading yet.
    every language in this list is a dictionary with the following info:
                id = unique id of the language;
                language = <unicode string>
    """

    all_languages = Language.available_languages()
    all_languages.sort(key=lambda x: x.name)
    learned_languages = Language.all_reading_for_user(flask.g.user)

    interesting_languages = []

    for lan in all_languages:
        if lan not in learned_languages:
            interesting_languages.append(lan.as_dictionary())

    return json_result(interesting_languages)
