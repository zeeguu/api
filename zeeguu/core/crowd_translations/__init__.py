from zeeguu.core.model import Language, Text, Bookmark


def get_own_past_translation(
        user, word: str, from_lang_code: str, to_lang_code, context_str: str
):
    to_language = Language.find(to_lang_code)
    from_language = Language.find(from_lang_code)

    ocurrences_of_context = Text.find_all(context_str, from_language)
    # might be occuring in different articles (very unlikely)
    # but the text is the same;
    # might have a translation in one of the articles, but
    # not in the others...

    for each_context in ocurrences_of_context:
        for bookmark in Bookmark.find_all_for_text_and_user(each_context, user):
            if (
                    bookmark.origin.word == word
                    and bookmark.translation.language == to_language
            ):
                return bookmark

    return None
