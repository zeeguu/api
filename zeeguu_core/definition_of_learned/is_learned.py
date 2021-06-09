CORRECTS_IN_DISTINCT_DAYS_FOR_LEARNED = 4


def is_learned_based_on_exercise_outcomes(exercise_log):
    """
    :return:
    """
    if exercise_log.is_empty():
        return False

    return (
        exercise_log.last_exercise().is_too_easy()
        or len(exercise_log.most_recent_correct_dates())
        >= CORRECTS_IN_DISTINCT_DAYS_FOR_LEARNED
    )
