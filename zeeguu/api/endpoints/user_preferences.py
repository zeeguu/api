import flask

import zeeguu.core

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from . import api
from ...core.model import UserPreference


@api.route("/user_preferences", methods=["GET"])
@cross_domain
@with_session
def user_preferences():
    preferences = {}

    for each in UserPreference.all_for_user(flask.g.user):
        preferences[each.key] = each.value

    return json_result(preferences)


@api.route("/save_user_preferences", methods=["POST"])
@cross_domain
@with_session
def save_user_preferences():

    data = flask.request.form

    audio_exercises_value = data.get(UserPreference.AUDIO_EXERCISES, None)
    if audio_exercises_value:
        pref = UserPreference.find_or_create(
            zeeguu.core.model.db.session, flask.g.user, UserPreference.AUDIO_EXERCISES
        )
        pref.value = audio_exercises_value
        zeeguu.core.model.db.session.add(pref)

    zeeguu.core.model.db.session.add(flask.g.user)
    zeeguu.core.model.db.session.commit()
    return "OK"
