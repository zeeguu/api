import flask

from zeeguu.core.model import UserExerciseSession

from zeeguu.api.utils.route_wrappers import requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session
from flask import request
from datetime import datetime
from .helpers.activity_sessions import update_activity_session
from zeeguu.core.emailer.user_activity import (
    send_user_finished_exercise_session,
)


@api.route(
    "/exercise_session_start",
    methods=["POST"],
)
@requires_session
def exercise_session_start():
    platform = request.form.get("platform", None)
    if platform is not None:
        platform = int(platform)
    session = UserExerciseSession(flask.g.user_id, datetime.now(), platform=platform)
    db_session.add(session)
    db_session.commit()
    return json_result(dict(id=session.id))


@api.route(
    "/exercise_session_update",
    methods=["POST"],
)
@requires_session
def exercise_session_update():
    session = update_activity_session(UserExerciseSession, request, db_session)
    return json_result(dict(id=session.id, duration=session.duration))


@api.route(
    "/exercise_session_end",
    methods=["POST"],
)
@requires_session
def exercise_session_end():
    from zeeguu.core.sql.learner.exercises_history import exercises_in_session

    session = update_activity_session(UserExerciseSession, request, db_session)

    # Check if any exercises were done in this session
    exercises = exercises_in_session(session.id)
    if not exercises:
        # Delete empty sessions - no point in keeping them
        db_session.delete(session)
        db_session.commit()
        return "OK"

    send_user_finished_exercise_session(session)
    return "OK"


@api.route(
    "/exercise_session_info/<id>",
    methods=["GET"],
)
@requires_session
def exercise_session_info(id):
    session = UserExerciseSession.find_by_id(id)
    return json_result(dict(id=session.id, duration=session.duration))
