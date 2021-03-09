import itertools
import traceback

from MySQLdb._exceptions import IntegrityError

import zeeguu_core
from zeeguu_core.model.bookmark_priority_arts import BookmarkPriorityARTS
from zeeguu_core.model.exercise import Exercise
from zeeguu_core.model.exercise_source import ExerciseSource
from zeeguu_core.model.learner_stats.exercise_stats import ExerciseStats
from zeeguu_core.util.timer_logging_decorator import time_this
from zeeguu_core.word_scheduling.arts.algorithm_wrapper import AlgorithmWrapper
from zeeguu_core.word_scheduling.arts.analysis.normal_distribution import NormalDistribution
from zeeguu_core.word_scheduling.arts.arts_rt import ArtsRT
from sentry_sdk import capture_exception, capture_message

db = zeeguu_core.db


class PriorityInfo:
    """
    a useful triple...
    """
    MAX_PRIORITY = 1000
    NO_PRIORITY = -1000

    def __init__(self, bookmark, exercise, priority=MAX_PRIORITY):
        self.bookmark = bookmark
        self.exercise = exercise
        self.priority = priority


class BookmarkPriorityUpdater:
    """

    Handles the related tasks for using word scheduling algorithms
    and also acts as a wrapper that calls the specific algorithm

        update_bookmark_priority

    """

    algorithm_wrapper = AlgorithmWrapper(ArtsRT())

    @classmethod
    @time_this
    def update_bookmark_priority(cls, db, user):
        """ Update all bookmark priorities of one user

        :param db: The connection to the database
        :param user: The user object
        """
        try:
            bookmarks_for_user = user.all_bookmarks_fit_for_study()
            fit_for_study_count = len(bookmarks_for_user)

            zeeguu_core.log(f"{fit_for_study_count} bookmarks fit for study")
            if fit_for_study_count == 0:
                return

            # tuple(0=bookmark, 1=exercise)
            bookmark_exercise_of_user = map(cls._get_exercise_of_bookmark, bookmarks_for_user)
            b1, b2 = itertools.tee(bookmark_exercise_of_user, 2)

            max_iterations = max(pair.exercise.id if pair.exercise is not None else 0 for pair in b1)

            exercises_and_priorities = [cls._calculate_bookmark_priority(x, max_iterations) for x in b2]

            # with db.session.no_autoflush:  # might not be needed, but just to be safe
            for each in exercises_and_priorities:
                entry = BookmarkPriorityARTS.find_or_create(each.bookmark, each.priority)
                zeeguu_core.log(
                    f"Updating {each.bookmark.id} with priority: {each.priority} from: {entry.priority}")
                entry.priority = each.priority

                max_retries = 3

                while True:

                    try:
                        db.session.add(entry)
                        db.session.commit()
                        break
                    except IntegrityError:
                        db.session.rollback()
                        capture_message("conflict in saving bookmark priority; will retry")
                        max_retries -= 1
                        if max_retries < 1:
                            raise



        except Exception as e:
            db.session.rollback()
            capture_exception(e)
            print('Error during updating bookmark priority')
            print(e)
            print(traceback.format_exc())

    @classmethod
    def _update_exercise_source_stats(cls):
        """Update the ExerciseStats for the ArtsDiffSlow and ArtsDiffFast algorithm to provide
         normalization information between the different exercise sources"""
        exercise_sources = list(ExerciseSource.query.all())
        for source in exercise_sources:
            exercises = Exercise.query.filter_by(source_id=source.id).filter(Exercise.solving_speed <= 30000).all()
            reaction_times = list(map(lambda x: x.solving_speed, exercises))
            if len(reaction_times) == 0:
                # magic values for the reaction, if no data exists
                reaction_times = [5000, 6000]
                print('This exercise source has no data yet. ID: ' + str(source.id))

            mean, sd = NormalDistribution.calc_normal_distribution(
                reaction_times)
            if sd is None:
                sd = 1000
            exercise_stats = ExerciseStats.find_or_create(db.session, ExerciseStats(source, mean, sd))
            db.session.merge(exercise_stats)

        db.session.commit()

    @classmethod
    def _calculate_bookmark_priority(cls, x, max_iterations):
        """Calculate the (new) priority of a bookmark-exercise pair

        :param x: An instance of the bookmark-exercise information (PriorityInfo)
        :param max_iterations: The current amount of iterations/learning sessions (in the ArtsRT algorithm known as D)
        :return: The bookmark-exercise information (PriorityInfo) with a updated priority
        """
        if x.exercise is not None:

            if x.exercise.solving_speed > 0:
                x.priority = cls.algorithm_wrapper.calculate(x.exercise, max_iterations)

            else:
                # solving speed is -1 for the cases where there was some feedback
                # from the user (either that it's too easy, or that there's something
                # wrong with it. we shouldn't schedule the bookmark in this case.
                # moreover, even if we wanted we can't since there's a log of reaction
                # time somewhere and it won't work with -1!
                x.priority = PriorityInfo.NO_PRIORITY
        else:
            x.priority = PriorityInfo.MAX_PRIORITY
        return x

    @staticmethod
    def _get_exercise_of_bookmark(bookmark):
        if 0 < len(bookmark.exercise_log):
            return PriorityInfo(bookmark=bookmark, exercise=bookmark.exercise_log[-1])

        return PriorityInfo(bookmark=bookmark, exercise=None)
