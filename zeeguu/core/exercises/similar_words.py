import random

from zeeguu.core.word_stats import lang_info


def similar_words(word, language, user):

    words_the_user_must_study = user.scheduled_bookmarks(10)

    if len(words_the_user_must_study) == 10:
        candidates = [each.origin.word for each in words_the_user_must_study]
    else:
        candidates = lang_info(language.code).all_words()

    random_sample = random.sample(candidates, 2)
    while word in random_sample:
        random_sample = random.sample(candidates, 2)

    return random_sample
