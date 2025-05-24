from zeeguu.core.model import Language, Bookmark
from zeeguu.core.model.bookmark_context import BookmarkContext


def get_own_past_translation(
    user, word: str, from_lang_code: str, to_lang_code, context_str: str
):
    to_language = Language.find(to_lang_code)
    from_language = Language.find(from_lang_code)

    ocurrences_of_context = BookmarkContext.find_all(context_str, from_language)
    # might be occuring in different articles (very unlikely)
    # but the text is the same;
    # might have a translation in one of the articles, but
    # not in the others...

    for each_context in ocurrences_of_context:
        for bookmark in Bookmark.find_all_for_context_and_user(each_context, user):
            if (
                bookmark.user_meaning.meaning.origin.content == word
                and bookmark.user_meaning.meaning.translation.language == to_language
            ):
                return bookmark

    return None
