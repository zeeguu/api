from zeeguu.core.bookmark_quality.negative_qualities import bad_quality_bookmark


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
    from zeeguu.core.model import Bookmark

    other_bookmarks_in_this_context = Bookmark.find_all_for_text_and_user(
        context, bookmark.user
    )
    if len(other_bookmarks_in_this_context) > 2:
        return False

    # context not too long
    if len(context.content) > 140:
        return False

    return True
