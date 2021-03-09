from zeeguu_core.model import Bookmark, UserWord
from zeeguu_core.model.bookmark_priority_arts import BookmarkPriorityARTS
from zeeguu_core.word_scheduling.arts.ab_testing import ABTesting
from zeeguu_core import logger
from sqlalchemy import or_


def bookmarks_to_study(user, desired_bookmarks_count=10):
    """

        Returns a list of bookmarks with the highest priorities
        An equal amount of bookmarks from each used algorithm (ABTesting) are selected


        Otherwise, an equal amount of bookmarks is taken from each bookmark_group and concatenated into a list,
        which is then returned. The amount of bookmarks taken from each group can differ by 1, depending on whether the
        possible_bookmarks_to_return_count is equally dividable by the group count.

    """
    bookmarks = (Bookmark.query.
                 filter_by(user_id=user.id).
                 filter_by(learned=False).
                 join(BookmarkPriorityARTS, BookmarkPriorityARTS.bookmark_id == Bookmark.id).
                 join(UserWord, Bookmark.origin_id == UserWord.id).
                 filter(or_(Bookmark.fit_for_study == True, Bookmark.starred == True)).
                 filter(UserWord.language_id == user.learned_language_id).
                 order_by(BookmarkPriorityARTS.priority.desc()).
                 all())

    # Group the bookmarks by their used priority algorithm in lists
    bookmark_groups = ABTesting.split_bookmarks_based_on_algorithm(bookmarks)
    if len(bookmarks) == 0:
        logger.info("Zero bookmarks to study")
        return []

    group_count = len(bookmark_groups)
    logger.info(f"Bookmark groups: {group_count}")
    if group_count == 0:
        return []

    # Select bookmarks from the algorithm groups
    bookmarks_to_return = []
    possible_bookmarks_to_return_count = min(desired_bookmarks_count, len(bookmarks))
    i = 0  # counter to select from different groups
    while possible_bookmarks_to_return_count != len(bookmarks_to_return):
        idx = i % len(bookmark_groups)
        if 0 < len(bookmark_groups[idx]):
            bookmarks_to_return.append(bookmark_groups[idx].pop(0))

        if i >= len(bookmarks):
            # no more bookmarks available...
            break
        i = i + 1

    return bookmarks_to_return
