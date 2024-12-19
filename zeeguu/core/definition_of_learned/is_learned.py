from zeeguu.api.endpoints.feature_toggles import is_feature_enabled_for_user

from zeeguu.core.word_scheduling import (
    TwoLearningCyclesPerWord,
    FourLevelsPerWord,
)


def is_learned_based_on_exercise_outcomes(exercise_log, is_productive=True):
    """
    Checks if the user has reported the exercise as too easy or looks into the
    streaks of this exercise log. Currently (14/06/2024), Zeeguu uses 2 cycles of
    4 different days in spaced repetition to consider a word learned.

    If a user has 2 streaks of 4, it means they have completed two full cycles,
    and therefore have learned the word.

    The user also has the option of saying they do not want productive exercises.
    In this case, we only need to have a single streak of 4 to consider the bookmark
    learned.

    :return:Boolean, the bookmark is learned based on the exercises or not.
    """
    if exercise_log.is_empty():
        return False

    if exercise_log.last_exercise().is_too_easy():
        return True

    # For a bookmark to be learned it needs to have 1 or 2 cycles
    # completed depending on the user preference.

    scheduler = get_scheduler(exercise_log.bookmark.user)

    learning_cycle_length = len(scheduler.get_cooling_interval_dictionary())

    streak_counts = exercise_log.count_number_of_streaks()
    full_cycles_completed = streak_counts.get(learning_cycle_length)

    if is_productive:
        return full_cycles_completed == 2
    else:
        return full_cycles_completed == 1


def get_scheduler(user):

    if is_feature_enabled_for_user("exercise_levels", user):
        return FourLevelsPerWord
    else:
        return TwoLearningCyclesPerWord
