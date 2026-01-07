from zeeguu.core.model.meaning import MeaningFrequency, PhraseType


def bad_quality_bookmark(bookmark):
    return (
        origin_is_subsumed_in_other_bookmark(bookmark)
        or context_is_too_long(bookmark)
        or translation_already_in_context_bug(bookmark)
        or word_not_in_context(bookmark)
    )


def uncommon_word_for_beginner_user(user_word):
    from zeeguu.core.model import UserLanguage

    user_language = UserLanguage.query.filter_by(
        user=user_word.user, language=user_word.user.learned_language
    ).first()

    if user_language and user_language.cefr_level:
        if user_language.cefr_level in ["A1", "A2"]:
            if user_word.meaning.frequency and user_word.meaning.frequency in [
                MeaningFrequency.UNCOMMON,
                MeaningFrequency.RARE,
            ]:
                return True
    return False


def bad_quality_meaning(user_word):
    bookmarks = user_word.bookmarks()
    return (
        uncommon_word_for_beginner_user(user_word)
        or arbitrary_multi_word_translation(user_word)
        or origin_same_as_translation(user_word)
        or origin_has_too_many_words(user_word)
        or origin_is_a_very_short_word(user_word)
        or (bookmarks and all([bad_quality_bookmark(b) for b in bookmarks]))
    )


def arbitrary_multi_word_translation(user_word):
    return user_word.meaning.phrase_type == PhraseType.ARBITRARY_MULTI_WORD


def context_is_too_long(bookmark):
    words = _split_words_from_context(bookmark)

    return len(words) > 42


def origin_is_a_very_short_word(user_word):
    return len(user_word.meaning.origin.content) < 3


def origin_has_too_many_words(user_word):
    words_in_origin = user_word.meaning.origin.content.split(" ")
    return len(words_in_origin) > 2


def origin_is_subsumed_in_other_bookmark(bookmark):
    """
    if the user translates a superset of this sentence
    """
    from zeeguu.core.model.bookmark import Bookmark

    all_bookmarks_in_text = Bookmark.find_all_for_context_and_user(
        bookmark.context, bookmark.user_word.user
    )

    for each in all_bookmarks_in_text:
        if each != bookmark:
            if (
                bookmark.user_word.meaning.origin.content
                in each.user_word.meaning.origin.content
            ):
                return True
        return False


def origin_same_as_translation(user_word):

    return (
        user_word.meaning.origin.content.lower()
        == user_word.meaning.translation.content.lower()
    )


def translation_already_in_context_bug(bookmark):
    # a superset of translation same as origin...
    # happens in the case of some bugs in translation
    # where the translation is inserted in the text
    # till we fix it, we should not show this

    if bookmark.user_word.meaning.translation.content in bookmark.get_context():
        return True


def word_not_in_context(bookmark):
    """
    Check if the word being learned doesn't appear in the context.

    This can happen due to:
    - Accent/diacritic variations (orienté vs oriente)
    - Verb conjugations (hatte vs hätte)
    - Unicode corruption (bad vs båd)

    These bookmarks cannot be properly highlighted in exercises.
    """
    import unicodedata

    try:
        word = bookmark.user_word.meaning.origin.content
        context = bookmark.get_context()

        # Normalize both for fair comparison
        word_norm = unicodedata.normalize('NFC', word).lower()
        context_norm = unicodedata.normalize('NFC', context).lower()

        return word_norm not in context_norm
    except Exception:
        # If we can't check, assume it's OK (fail open)
        return False


def _split_words_from_context(bookmark):
    import re

    result = []
    bookmark_content_words = re.findall(r"(?u)\w+", bookmark.get_context())
    for word in bookmark_content_words:
        if word.lower() != bookmark.user_word.meaning.origin.content.lower():
            result.append(word)

    return result
