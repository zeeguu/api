def bad_quality_bookmark(bookmark):

    return (
        origin_same_as_translation(bookmark)
        or origin_is_subsumed_in_other_bookmark(bookmark)
        or origin_has_too_many_words(bookmark)
        or origin_is_a_very_short_word(bookmark)
        or context_is_too_long(bookmark)
        or translation_already_in_context_bug(bookmark)
    )


def split_words_from_context(bookmark):
    import re

    result = []
    bookmark_content_words = re.findall(r"(?u)\w+", bookmark.get_context())
    for word in bookmark_content_words:
        if word.lower() != bookmark.meaning.origin.word.lower():
            result.append(word)

    return result


def context_is_too_long(bookmark):
    words = split_words_from_context(bookmark)

    return len(words) > 42


def origin_is_a_very_short_word(bookmark):
    return len(bookmark.meaning.origin.word) < 3


def origin_has_too_many_words(bookmark):
    words_in_origin = bookmark.meaning.origin.word.split(" ")
    return len(words_in_origin) > 2


def origin_is_subsumed_in_other_bookmark(self):
    """
    if the user translates a superset of this sentence
    """
    from zeeguu.core.model.bookmark import Bookmark

    all_bookmarks_in_text = Bookmark.find_all_for_context_and_user(
        self.context, self.user
    )

    for each in all_bookmarks_in_text:
        if each != self:
            if self.meaning.origin.word in each.meaning.origin.word:
                return True
        return False


def origin_same_as_translation(self):
    try:
        return self.meaning.origin.word.lower() == self.meaning.translation.word.lower()
    except:
        print("missing word for bookmark with id {0}".format(self.id))
        return False


def translation_already_in_context_bug(self):
    # a superset of translation same as origin...
    # happens in the case of some bugs in translation
    # where the translation is inserted in the text
    # till we fix it, we should not show this

    if self.meaning.translation.word in self.get_context():
        return True
