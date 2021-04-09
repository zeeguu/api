import random

from wordstats import LanguageInfo


def similar_words(bookmark, user):

    words_the_user_must_study = user.bookmarks_to_study()

    if len(words_the_user_must_study) > 10:
        candidates = words_the_user_must_study
    else:
        learned_language = LanguageInfo.load(bookmark.origin.language.code)
        candidates = learned_language.all_words()

    return random.sample(candidates, 2)
