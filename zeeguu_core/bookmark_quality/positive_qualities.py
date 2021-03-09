import zeeguu_core
from zeeguu_core.bookmark_quality.negative_qualities import bad_quality_bookmark


def quality_bookmark(bookmark):
    return not bad_quality_bookmark(bookmark)


def quality_top_bookmark(bookmark):
    """

        used in the top bookmarks
        differs a bit from the exercises...
        although it could be decided to merge them in the future

    """
    context = bookmark.text

    # word should not be too short
    if len(bookmark.origin.word) < 5:
        return False

    # if there are other bookmarks in this context
    # it is not an ideal context, since the user
    # might not understand the context
    if multiple_bookmarks_for_same_context(bookmark):
        return False

    # context not too long
    if len(context.content) > 140:
        return False

    return True


def multiple_bookmarks_for_same_context(self):
    return len(self.text.all_bookmarks(self))
