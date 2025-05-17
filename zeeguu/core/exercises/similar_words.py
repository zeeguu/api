import random

from zeeguu.core.word_stats import lang_info
from zeeguu.core.word_filter import (
    BAD_WORD_LIST,
    PROPER_NAMES_LIST,
    remove_words_based_on_list,
)


def similar_words(word, language, user, number_of_words_to_return=2):

    from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

    words_the_user_must_study = BasicSRSchedule.scheduled_bookmarks(user, None, 10)

    if len(words_the_user_must_study) == 10:
        candidates = [each.origin.word for each in words_the_user_must_study]
    else:
        candidates = lang_info(language.code).all_words()
        candidates_filtered = remove_words_based_on_list(candidates, BAD_WORD_LIST)
        candidates_filtered = remove_words_based_on_list(
            candidates_filtered, PROPER_NAMES_LIST
        )
        # Update candidates to be based on the filtered words.
        candidates = [w for w in candidates_filtered if len(w) > 1]

    random_sample = random.sample(candidates, number_of_words_to_return)
    while word in random_sample:
        random_sample = random.sample(candidates, number_of_words_to_return)

    return random_sample
