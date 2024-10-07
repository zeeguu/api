from .profanity_filter import load_bad_words
from .proper_noun_filter import load_proper_name_list

BAD_WORD_LIST = load_bad_words()
PROPER_NAMES_LIST = load_proper_name_list()


def remove_words_based_on_list(candidates, words_to_remove_list):
    return list(set(candidates) - set(words_to_remove_list))
