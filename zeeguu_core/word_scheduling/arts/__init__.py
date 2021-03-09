"""

    ARTS algorithm as described in:

        Adaptive response-time-based category sequencing in perceptual learning
        by Everett Mettler and Philip J. Kellman

    The main two public methods of this package are:

           bookmarks_to_study
               returns a list of bookmarks to study

            update_bookmark_priority
                this can be time consuming, so the caller might want
                to call it separately; in theory they can also call
                it before every call to bookmarks_to_study by setting
                the corresponding method argument in that method to True

     Original Implementation by Timon Back and Peter Ullrich
"""
from zeeguu_core.util.timer_logging_decorator import time_this
from zeeguu_core.word_scheduling.arts.experiments.arts_diff_fast import ArtsDiffFast
from zeeguu_core.word_scheduling.arts.experiments.arts_random import ArtsRandom
from . import bookmark_priority_updater
from . import words_to_study
from .arts_rt import ArtsRT


def bookmarks_to_study(user, desired_bookmarks_count=10, db=None, compute_priority_before=False):
    """

        Note that updating bookmark priority might be slow; this is by default turned off...

    :param user:
    :param desired_bookmarks_count:
    :param db: can be none if one needs not update the priorities beforehand
    :param compute_priority_before:
    :return:
    """

    if compute_priority_before:
        update_bookmark_priority(db, user)

    return words_to_study.bookmarks_to_study(user, desired_bookmarks_count)


def update_bookmark_priority(db, user):
    return bookmark_priority_updater.BookmarkPriorityUpdater.update_bookmark_priority(db, user)
