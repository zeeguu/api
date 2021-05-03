import random

from zeeguu_core.word_stats import lang_info


def similar_words(bookmark, user):

    words_the_user_must_study = user.bookmarks_to_study(10)

    if len(words_the_user_must_study) == 10:
        candidates = [each.origin.word for each in words_the_user_must_study]
    else:
        candidates = lang_info(bookmark.origin.language.code).all_words()

    return random.sample(candidates, 2)
