import random

from zeeguu.core.word_stats import lang_info
from zeeguu.core.word_filter import (
    BAD_WORD_LIST,
    PROPER_NAMES_LIST,
    remove_words_based_on_list,
)


def similar_words(word, language, user, words_to_sample=2):

    words_the_user_must_study = user.scheduled_bookmarks(10)

    if len(words_the_user_must_study) == 10:
        candidates = [each.origin.word for each in words_the_user_must_study]
    else:
        candidates = lang_info(language.code).all_words()
        candidates_filtered = remove_words_based_on_list(candidates, BAD_WORD_LIST)
        candidates_filtered = remove_words_based_on_list(
            candidates_filtered, PROPER_NAMES_LIST
        )
        candidates_filtered = [w for w in candidates_filtered if len(w) > 1]

    random_sample = random.sample(candidates_filtered, words_to_sample)
    while word in random_sample:
        random_sample = random.sample(candidates_filtered, words_to_sample)

    return random_sample
