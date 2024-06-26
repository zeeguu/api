from zeeguu.core.bookmark_quality import quality_bookmark
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference


def fit_for_study(bookmark):
    return (
        quality_bookmark(bookmark)
        or bookmark.user_preference == UserWordExPreference.USE_IN_EXERCISES
    ) and not bookmark.user_preference == UserWordExPreference.DONT_USE_IN_EXERCISES


def feedback_prevents_further_study(exercise_log):
    last_outcome = exercise_log.latest_exercise_outcome()

    if not last_outcome:
        return False

    return last_outcome.free_text_feedback() or last_outcome.too_easy()
