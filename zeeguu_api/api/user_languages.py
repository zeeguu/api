import flask
import zeeguu
from flask import request
from zeeguu.model.language import Language
from zeeguu.model.user_language import UserLanguage


from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api

session = zeeguu.db.session

USER_LANGUAGES = "user_languages"
ADD_USER_LANGUAGE = "user_languages/add"
DELETE_USER_LANGUAGE = "user_languages/delete"
INTERESTING_LANGUAGES = "user_languages/interesting"
READING_LANGUAGES = "user_languages/reading"


# ---------------------------------------------------------------------------
@api.route(f"/{ADD_USER_LANGUAGE}", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def add_user_language():
    """
    This endpoint is for adding a user language.
    It tries to find the user_language, and otherwise create it.
    After that set it to reading_news so it appears in the reader.

    :return: "OK" in case of success
    """
    language_id = int(request.form.get('language_id', ''))

    language_object = Language.find_by_id(language_id)
    user_language = UserLanguage.find_or_create(session, flask.g.user, language_object)
    user_language.set_reading_news()
    session.add(user_language)
    session.commit()

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{DELETE_USER_LANGUAGE}/<language_id>", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def delete_user_language(language_id):
    """
    A user can delete a language with a given ID.
    At the moment this endpoint is used for deleting it from the reader,
    not actually deleting the user language, as it might still be used
    somewhere else or later on.

    :return: OK / ERROR
    """

    try:
        language = UserLanguage.with_language_id(language_id, flask.g.user)
        language.stop_reading_news()
        session.add(language)
        session.commit()
    except Exception as e:
        return "OOPS. SEARCH AIN'T THERE IT SEEMS (" + str(e) + ")"

    return "OK"


# ---------------------------------------------------------------------------
@api.route(f"/{USER_LANGUAGES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_user_languages():
    """
    A user might be subscribed to multiple languages at once.
    This endpoint returns them as a list.

    :return: a json list with searches for which the user is registered;
     every search in this list is a dictionary with the following info:
                id = unique id of the topic;
                language = <unicode string>
    """
    all_user_languages = []
    user_languages = UserLanguage.get_all_user_languages(flask.g.user)
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

    :return: a json list with searches for which the user is registered;
     every search in this list is a dictionary with the following info:
                id = unique id of the topic;
                language = <unicode string>
    """
    all_user_languages = []
    reading_languages = UserLanguage.get_all_reading_languages(flask.g.user)
    for lan in reading_languages:
        all_user_languages.append(lan.as_dictionary())
    return json_result(all_user_languages)


# ---------------------------------------------------------------------------
@api.route(f"/{INTERESTING_LANGUAGES}", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_interesting_languages():
    """
    'Interesting languages' are defined as languages the user
    isn't subscribed to already and thus might subscribe to.

    :return: "OK" in case of success
    """

    all_languages = Language.available_languages()
    learned_languages = UserLanguage.get_all_reading_languages(flask.g.user)

    interesting_languages = []

    for lan in all_languages:
        if lan not in learned_languages:
            interesting_languages.append(lan.as_dictionary())

    return json_result(interesting_languages)
