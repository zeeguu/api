import flask

import zeeguu.core

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api
from ...core.model import UserPreference, User

db_session = zeeguu.core.model.db.session


@api.route("/user_preferences", methods=["GET"])
@cross_domain
@requires_session
def user_preferences():
    preferences = {}
    user = User.find_by_id(flask.g.user_id)
    for each in UserPreference.all_for_user(user):
        preferences[each.key] = each.value

    return json_result(preferences)


@api.route("/save_user_preferences", methods=["POST"])
@cross_domain
@requires_session
def save_user_preferences():
    data = flask.request.form
    user = User.find_by_id(flask.g.user_id)
    audio_exercises_value = data.get(UserPreference.AUDIO_EXERCISES, None)
    if audio_exercises_value:
        pref = UserPreference.find_or_create(
            db_session, user, UserPreference.AUDIO_EXERCISES
        )
        pref.value = audio_exercises_value
        db_session.add(pref)

    productive_exercises_value = data.get(UserPreference.PRODUCTIVE_EXERCISES, None)
    if productive_exercises_value:
        pref_productive = UserPreference.find_or_create(
            db_session,
            user,
            UserPreference.PRODUCTIVE_EXERCISES,
        )
        pref_productive.value = productive_exercises_value
        db_session.add(pref_productive)

    translate_reader_value = data.get(UserPreference.TRANSLATE_IN_READER, None)
    if translate_reader_value:
        translate_reader = UserPreference.find_or_create(
            db_session,
            user,
            UserPreference.TRANSLATE_IN_READER,
        )
        translate_reader.value = translate_reader_value
        db_session.add(translate_reader)

    pronounce_reader_value = data.get(UserPreference.PRONOUNCE_IN_READER, None)
    if pronounce_reader_value:
        pronounce_reader = UserPreference.find_or_create(
            db_session,
            user,
            UserPreference.PRONOUNCE_IN_READER,
        )
        pronounce_reader.value = pronounce_reader_value
        db_session.add(pronounce_reader)

    db_session.add(user)
    db_session.commit()
    return "OK"
