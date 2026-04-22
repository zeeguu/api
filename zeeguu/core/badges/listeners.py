from zeeguu.core import events
from zeeguu.core.badges.badge_progress import update_metric_and_award_badges
from zeeguu.core.model import User, UserLanguage
from zeeguu.core.model.badge_category import ActivityMetric
from zeeguu.core.model.friend import Friend


@events.word_translated.connect
def on_word_translated(sender, user_id: int, db_session):
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.TRANSLATED_WORDS,
        user_id
    )


@events.exercise_correct.connect
def on_exercise_correct(sender, user_id: int, db_session):
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.CORRECT_EXERCISES,
        user_id
    )


@events.audio_lesson_completed.connect
def on_audio_lesson_completed(sender, user_id: int, db_session):
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.COMPLETED_AUDIO_LESSONS,
        user_id
    )


@events.streak_changed.connect
def on_streak_changed(sender, user_id: int, db_session):
    user = User.find_by_id(user_id)
    if not user:
        return
    current_value = max(
        [
            user_language.current_daily_streak
            for user_language in UserLanguage.all_user_languages_for_user(user, db_session)
        ]
    )
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.STREAK_DAYS,
        user_id,
        current_value
    )


@events.word_learned.connect
def on_word_learned(sender, user_id: int, db_session):
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.LEARNED_WORDS,
        user_id
    )


@events.article_read.connect
def on_article_read(sender, user_id: int, db_session):
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.READ_ARTICLES,
        user_id
    )


@events.friendship_changed.connect
def on_friendship_changed(sender, user_id: int, db_session):
    current_value = Friend.count_active_friends(user_id, db_session)
    update_metric_and_award_badges(
        db_session,
        ActivityMetric.FRIENDS,
        user_id,
        current_value
    )
