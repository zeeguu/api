from zeeguu.core.bookmark_quality import quality_meaning
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference


def fit_for_study(user_word):
    # Convert user_preference to int for comparison (handles string/int type mismatch from DB)
    preference = int(user_word.user_preference or 0)

    # Separated MWEs (multi-word expressions with words between parts) are not fit for study
    # because fill-in-the-blank exercises don't work well with non-adjacent words
    if _is_separated_mwe(user_word):
        return False

    return (
        quality_meaning(user_word)
        or preference == UserWordExPreference.USE_IN_EXERCISES
    ) and preference >= UserWordExPreference.NO_PREFERENCE


def _is_separated_mwe(user_word):
    """Check if the user_word's preferred bookmark is a separated MWE."""
    if user_word.preferred_bookmark is None:
        return False
    return user_word.preferred_bookmark.mwe_partner_token_i is not None


def feedback_prevents_further_study(exercise_log):
    last_outcome = exercise_log.latest_exercise_outcome()

    if not last_outcome:
        return False

    return last_outcome.free_text_feedback() or last_outcome.too_easy()
