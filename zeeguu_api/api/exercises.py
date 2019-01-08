import traceback
from datetime import datetime
import flask

import zeeguu_core
from zeeguu_core.model import Bookmark, Exercise, ExerciseOutcome, ExerciseSource
from zeeguu_core.word_scheduling.arts.bookmark_priority_updater import BookmarkPriorityUpdater

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from . import api, db_session


@api.route("/bookmarks_to_study/<bookmark_count>", methods=["GET"])
@cross_domain
@with_session
def bookmarks_to_study(bookmark_count):
    """
    Returns a number of <bookmark_count> bookmarks that
    are recommended for this user to study

    """

    int_count = int(bookmark_count)
    to_study = flask.g.user.bookmarks_to_study(int_count)
    if not to_study:
        # We might be in the situation of the priorities never having been
        # computed since theuser never did an exercise, and currently only
        # then are priorities recomputed; thus, in this case, we try to
        # update, and maybe this will solve the problem
        zeeguu_core.log("recomputting bookmark priorities since there seem to be no bookmarks to study")
        BookmarkPriorityUpdater.update_bookmark_priority(zeeguu_core.db, flask.g.user)
        to_study = flask.g.user.bookmarks_to_study(int_count)

    as_json = [bookmark.json_serializable_dict() for bookmark in to_study]
    return json_result(as_json)


@api.route("/get_exercise_log_for_bookmark/<bookmark_id>", methods=("GET",))
@cross_domain
@with_session
def get_exercise_log_for_bookmark(bookmark_id):
    bookmark = Bookmark.query.filter_by(id=bookmark_id).first()

    exercise_log_dict = []
    exercise_log = bookmark.exercise_log
    for exercise in exercise_log:
        exercise_log_dict.append(dict(id=exercise.id,
                                      outcome=exercise.outcome.outcome,
                                      source=exercise.source.source,
                                      exercise_log_solving_speed=exercise.solving_speed,
                                      time=exercise.time.strftime('%m/%d/%Y')))

    return json_result(exercise_log_dict)


@api.route("/report_exercise_outcome/<exercise_outcome>/<exercise_source>/<exercise_solving_speed>/<bookmark_id>",
           methods=["POST"])
@with_session
def report_exercise_outcome(exercise_outcome, exercise_source, exercise_solving_speed, bookmark_id):
    """
    In the model parlance, an exercise is an entry in a table that
    logs the performance of an exercise. Every such performance, has a source, and an outcome.

    :param exercise_outcome: One of: Correct, Retry, Wrong, Typo, Too easy
    :param exercise_source: has been assigned to your app by zeeguu
    :param exercise_solving_speed: in milliseconds
    :param bookmark_id: the bookmark for which the data is reported
    :return:
    """

    try:
        bookmark = Bookmark.find(bookmark_id)
        new_source = ExerciseSource.find(exercise_source)
        new_outcome = ExerciseOutcome.find_or_create(db_session, exercise_outcome)

        if not bookmark:
            return "could not find bookmark"

        if not new_source:
            return "could not find source"

        if not new_outcome:
            return "could not find outcome"

        exercise = Exercise(new_outcome, new_source, exercise_solving_speed, datetime.now())
        bookmark.add_new_exercise(exercise)
        bookmark.update_fit_for_study(db_session)
        bookmark.update_learned_status(db_session)
        db_session.add(exercise)
        db_session.commit()

        # Update the exercise session
        from zeeguu_core.model import UserExerciseSession
        UserExerciseSession.update_exercise_session(exercise, db_session)

        zeeguu_core.log("recomputting bookmark priorities")
        BookmarkPriorityUpdater.update_bookmark_priority(zeeguu_core.db, flask.g.user)

        return "OK"
    except:
        traceback.print_exc()
        return "FAIL"
