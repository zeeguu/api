from zeeguu.core.word_scheduling.basicSR.basicSR import NEXT_COOLING_INTERVAL_ON_SUCCESS

LEARNING_CYCLE_LENGTH = len(NEXT_COOLING_INTERVAL_ON_SUCCESS)


def is_learned_based_on_exercise_outcomes(exercise_log, is_productive=True):
    """
    Checks if the user has reported the exercise as too easy or looks into the
    streaks of this exercise log. Currently (14/06/2024), Zeeguu uses 2 cycles of
    4 different days in spaced repetition to concider a word learned.

    If a user has 2 streaks of 4, it means they have completed a 2 full cycles,
    and therefor have learned the word.

    The user also has the option of saying they do not want productive exercises.
    In this case, we only need to have a single streak of 4 to consider the bookmark
    learned.

    :return:Boolean, the bookmark is learned based on the exercises or not.
    """
    if exercise_log.is_empty():
        return False

    # For a bookmark to be learned it needs to have 1 or 2 cycles
    # completed depending on the user preference.
    if exercise_log.last_exercise().is_too_easy():
        return True

    streak_counts = exercise_log.count_number_of_streaks()
    full_cycles_completed = streak_counts.get(LEARNING_CYCLE_LENGTH)
    if is_productive:
        return full_cycles_completed == 2
    else:
        return full_cycles_completed == 1
