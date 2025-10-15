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
    user = User.find_by_id(flask.g.user_id)
    return json_result(UserPreference.all_for_user(user))


@api.route("/save_user_preferences", methods=["POST"])
@cross_domain
@requires_session
def save_user_preferences():
    data = flask.request.form
    user = User.find_by_id(flask.g.user_id)

    max_words_to_schedule_value = data.get(UserPreference.MAX_WORDS_TO_SCHEDULE, None)
    if max_words_to_schedule_value:
        # Validate and cap the value to prevent SQL errors
        validated_value = UserPreference.validate_max_words_to_schedule(
            max_words_to_schedule_value
        )
        pref = UserPreference.find_or_create(
            db_session, user, UserPreference.MAX_WORDS_TO_SCHEDULE
        )
        pref.value = str(validated_value)
        db_session.add(pref)

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

    filter_disturbing_content_value = data.get(UserPreference.FILTER_DISTURBING_CONTENT, None)
    if filter_disturbing_content_value:
        filter_disturbing_content = UserPreference.find_or_create(
            db_session,
            user,
            UserPreference.FILTER_DISTURBING_CONTENT,
        )
        filter_disturbing_content.value = filter_disturbing_content_value
        db_session.add(filter_disturbing_content)

    db_session.add(user)
    db_session.commit()
    return "OK"
