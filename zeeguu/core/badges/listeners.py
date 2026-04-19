from zeeguu.core import events
from zeeguu.core.badges.badge_progress import process_badge_event
from zeeguu.core.model import User, UserLanguage
from zeeguu.core.model.activity_type import ActivityTypeMetric
from zeeguu.core.model.friend import Friend


@events.word_translated.connect
def on_word_translated(sender, user_id: int, db_session):
    process_badge_event(
        db_session,
        ActivityTypeMetric.TRANSLATED_WORDS,
        user_id,
        increment_value=1,
    )


@events.exercise_correct.connect
def on_exercise_correct(sender, user_id: int, db_session):
    process_badge_event(
        db_session,
        ActivityTypeMetric.CORRECT_EXERCISES,
        user_id,
        increment_value=1,
    )


@events.audio_lesson_completed.connect
def on_audio_lesson_completed(sender, user_id: int, db_session):
    process_badge_event(
        db_session,
        ActivityTypeMetric.COMPLETED_AUDIO_LESSONS,
        user_id,
        increment_value=1,
    )


@events.streak_changed.connect
def on_streak_changed(sender, user_id: int, db_session):
    user = User.find_by_id(user_id)
    if not user:
        return
    current_value = max(
        [user_language.current_daily_streak for user_language in UserLanguage.all_user_languages_for_user(user)]
    )
    process_badge_event(
        db_session,
        ActivityTypeMetric.STREAK_DAYS,
        user_id,
        current_value=current_value,
    )


@events.word_learned.connect
def on_word_learned(sender, user_id: int, db_session):
    process_badge_event(
        db_session,
        ActivityTypeMetric.LEARNED_WORDS,
        user_id,
        increment_value=1,
    )


@events.article_read.connect
def on_article_read(sender, user_id: int, db_session):
    process_badge_event(
        db_session,
        ActivityTypeMetric.READ_ARTICLES,
        user_id,
        increment_value=1,
    )


@events.friendship_changed.connect
def on_friendship_changed(sender, user_id: int, db_session):
    current_value = Friend.count_active_friends(user_id)
    process_badge_event(
        db_session,
        ActivityTypeMetric.FRIENDS,
        user_id,
        current_value=current_value,
    )
