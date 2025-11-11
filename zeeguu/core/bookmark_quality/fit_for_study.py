from zeeguu.core.bookmark_quality import quality_meaning
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference


def fit_for_study(user_word):
    # Convert user_preference to int for comparison (handles string/int type mismatch from DB)
    preference = int(user_word.user_preference or 0)

    return (
        (
            quality_meaning(user_word)
            or preference == UserWordExPreference.USE_IN_EXERCISES
        )
        and not preference == UserWordExPreference.DONT_USE_IN_EXERCISES
    )


def feedback_prevents_further_study(exercise_log):
    last_outcome = exercise_log.latest_exercise_outcome()

    if not last_outcome:
        return False

    return last_outcome.free_text_feedback() or last_outcome.too_easy()
