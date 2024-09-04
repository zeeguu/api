import random

from zeeguu.core.word_stats import lang_info
from zeeguu.core.profanity_filter import BAD_WORD_LIST, remove_bad_words


def similar_words(word, language, user, words_to_sample=2):

    words_the_user_must_study = user.scheduled_bookmarks(10)

    if len(words_the_user_must_study) == 10:
        candidates = [each.origin.word for each in words_the_user_must_study]
    else:
        candidates = lang_info(language.code).all_words()
        candidates_filtered = remove_bad_words(candidates, BAD_WORD_LIST)

    if len(candidates_filtered) != len(candidates):
        word_set = set(candidates)
        print("WORDS Filtered: ", word_set.intersection(BAD_WORD_LIST))

    random_sample = random.sample(candidates_filtered, words_to_sample)
    while word in random_sample:
        random_sample = random.sample(candidates_filtered, words_to_sample)

    return random_sample
