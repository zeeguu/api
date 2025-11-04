from zeeguu.core.model.meaning import MeaningFrequency, PhraseType
from zeeguu.logging import logp


def bad_quality_bookmark(bookmark):
    return (
        origin_is_subsumed_in_other_bookmark(bookmark)
        or context_is_too_long(bookmark)
        or translation_already_in_context_bug(bookmark)
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
                logp(
                    f">>>> Found an uncommon word for beginner user {user_word.meaning.origin.content}. Marking it as not fit for study"
                )
                return True
    return False


def bad_quality_meaning(user_word):
    import time
    logp(f"[QUALITY-TIMING] bad_quality_meaning START for word='{user_word.meaning.origin.content}'")
    start_time = time.time()

    bookmarks = user_word.bookmarks()
    logp(f"[QUALITY-TIMING] Got {len(bookmarks)} bookmarks in {time.time() - start_time:.3f}s")

    check_start = time.time()
    result = (
        uncommon_word_for_beginner_user(user_word)
        or arbitrary_multi_word_translation(user_word)
        or origin_same_as_translation(user_word)
        or origin_has_too_many_words(user_word)
        or origin_is_a_very_short_word(user_word)
        or (bookmarks and all([bad_quality_bookmark(b) for b in bookmarks]))
    )
    logp(f"[QUALITY-TIMING] Quality checks took {time.time() - check_start:.3f}s, result={result}")
    logp(f"[QUALITY-TIMING] bad_quality_meaning TOTAL: {time.time() - start_time:.3f}s")

    return result


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
    import time

    logp(f"[QUALITY-TIMING] origin_is_subsumed_in_other_bookmark START for bookmark_id={bookmark.id}, context_id={bookmark.context_id}")
    start_time = time.time()

    all_bookmarks_in_text = Bookmark.find_all_for_context_and_user(
        bookmark.context, bookmark.user_word.user
    )

    logp(f"[QUALITY-TIMING] find_all_for_context_and_user returned {len(all_bookmarks_in_text)} bookmarks in {time.time() - start_time:.3f}s")

    for each in all_bookmarks_in_text:
        if each != bookmark:
            if (
                bookmark.user_word.meaning.origin.content
                in each.user_word.meaning.origin.content
            ):
                logp(f"[QUALITY-TIMING] origin_is_subsumed check TOTAL: {time.time() - start_time:.3f}s, result=True")
                return True
        logp(f"[QUALITY-TIMING] origin_is_subsumed check TOTAL: {time.time() - start_time:.3f}s, result=False")
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
