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
    from sqlalchemy.orm.exc import NoResultFound
    from ...core.model import Language, DailyAudioSubscription

    type_prefix = UserPreference.DAILY_AUDIO_LESSON_TYPE_PREFIX
    suggestion_prefix = UserPreference.DAILY_AUDIO_LESSON_SUGGESTION_PREFIX
    # Union of languages touched by EITHER key, so a suggestion-only save still
    # syncs the subscription (otherwise the legacy pref and the subscription drift).
    lang_codes = {key[len(type_prefix):] for key in data if key.startswith(type_prefix)} | {
        key[len(suggestion_prefix):] for key in data if key.startswith(suggestion_prefix)
    }
    for lang_code in lang_codes:
        # Resolve without find_or_create: that commits mid-request (and can create
        # a Language). These codes come from existing prefs, so find is enough.
        code = "zh-CN" if lang_code == "cn" else lang_code
        try:
            language = Language.find(code)
        except NoResultFound:
            continue

        type_key = UserPreference.daily_audio_lesson_type_key(lang_code)
        type_sent = type_key in data
        lesson_type = (data.get(type_key) or "").strip()
        raw_suggestion = (
            data.get(UserPreference.daily_audio_lesson_suggestion_key(lang_code)) or ""
        ).strip()[:128] or None
        sub = DailyAudioSubscription.find(user, language)

        if type_sent and not lesson_type:
            # Explicit empty type = turn off (config remembered).
            if sub is not None:
                sub.set_enabled(False)
        elif sub is not None:
            # Keep the existing type when only the suggestion changed.
            sub.configure(lesson_type or sub.lesson_type, raw_suggestion)
        elif lesson_type:
            db_session.add(DailyAudioSubscription(user, language, lesson_type, raw_suggestion))
        # else: suggestion-only with no existing subscription and no type — nothing to create.
