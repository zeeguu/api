def bad_quality_bookmark(bookmark):
    return (
        origin_is_subsumed_in_other_bookmark(bookmark)
        or context_is_too_long(bookmark)
        or translation_already_in_context_bug(bookmark)
    )


def bad_quality_meaning(user_word):

    return (
        origin_same_as_translation(user_word)
        or origin_has_too_many_words(user_word)
        or origin_is_a_very_short_word(user_word)
        or all([bad_quality_bookmark(b) for b in user_word.bookmarks()])
    )


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


def _split_words_from_context(bookmark):
    import re

    result = []
    bookmark_content_words = re.findall(r"(?u)\w+", bookmark.get_context())
    for word in bookmark_content_words:
        if word.lower() != bookmark.user_word.meaning.origin.content.lower():
            result.append(word)

    return result
