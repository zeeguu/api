from zeeguu.core.bookmark_quality import quality_bookmark
from zeeguu.core.definition_of_learned import is_learned_based_on_exercise_outcomes
from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog


def fit_for_study(bookmark):
    exercise_log = SortedExerciseLog(bookmark)

    return (

            (quality_bookmark(bookmark) or bookmark.starred) and

            not is_learned_based_on_exercise_outcomes(exercise_log) and

            not feedback_prevents_further_study(exercise_log)

    )


def feedback_prevents_further_study(exercise_log):
    last_outcome = exercise_log.latest_exercise_outcome()

    if not last_outcome:
        return False

    return (

            last_outcome.free_text_feedback() or

            last_outcome.too_easy()
    )
