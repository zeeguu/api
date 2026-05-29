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

    show_mwe_hints_value = data.get(UserPreference.SHOW_MWE_HINTS, None)
    if show_mwe_hints_value:
        show_mwe_hints = UserPreference.find_or_create(
            db_session,
            user,
            UserPreference.SHOW_MWE_HINTS,
        )
        show_mwe_hints.value = show_mwe_hints_value
        db_session.add(show_mwe_hints)

    show_reading_timer_value = data.get(UserPreference.SHOW_READING_TIMER, None)
    if show_reading_timer_value is not None:
        show_reading_timer = UserPreference.find_or_create(
            db_session,
            user,
            UserPreference.SHOW_READING_TIMER,
        )
        show_reading_timer.value = show_reading_timer_value
        db_session.add(show_reading_timer)

    # Daily audio lesson preferences are keyed per language (e.g. daily_audio_lesson_type_da,
    # daily_audio_lesson_suggestion_da). The suggestion is stored EXACTLY as the user typed it —
    # no canonicalization/normalization here; that happens later, at generation time.
    for key in data.keys():
        if key.startswith(
            UserPreference.DAILY_AUDIO_LESSON_TYPE_PREFIX
        ) or key.startswith(UserPreference.DAILY_AUDIO_LESSON_SUGGESTION_PREFIX):
            pref = UserPreference.find_or_create(db_session, user, key)
            pref.value = (data.get(key) or "")[:255]
            db_session.add(pref)

    # Mirror the legacy daily-audio keys into the first-class DailyAudioSubscription
    # (the source of truth for the cron and newer clients), keeping this endpoint
    # working for clients that still post the keys. Empty type = turn off.
    _mirror_daily_audio_subscriptions(user, data)

    db_session.add(user)
    db_session.commit()
    return "OK"


def _mirror_daily_audio_subscriptions(user, data):
    from ...core.model import Language, DailyAudioSubscription

    lang_codes = {
        key[len(UserPreference.DAILY_AUDIO_LESSON_TYPE_PREFIX):]
        for key in data.keys()
        if key.startswith(UserPreference.DAILY_AUDIO_LESSON_TYPE_PREFIX)
    }
    for lang_code in lang_codes:
        try:
            language = Language.find_or_create(lang_code)  # handles the cn→zh-CN quirk
        except Exception:
            continue
        lesson_type = (data.get(UserPreference.daily_audio_lesson_type_key(lang_code)) or "").strip()
        raw_suggestion = (
            data.get(UserPreference.daily_audio_lesson_suggestion_key(lang_code)) or ""
        ).strip() or None
        sub = DailyAudioSubscription.find(user, language)
        if lesson_type:
            if sub is None:
                db_session.add(DailyAudioSubscription(user, language, lesson_type, raw_suggestion))
            else:
                sub.configure(lesson_type, raw_suggestion)
        elif sub is not None:
            sub.set_enabled(False)
