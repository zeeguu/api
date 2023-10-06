import flask

from zeeguu.core.model import Bookmark, UserExerciseSession

from zeeguu.api.utils.route_wrappers import with_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session
from flask import request


@api.route(
    "/start_new_exercise_session",
    methods=["POST"],
)
@with_session
def start_new_exercise_session():
    from datetime import datetime
    session = UserExerciseSession(flask.g.user.id, datetime.now())
    db_session.add(session)
    db_session.commit()

    return json_result(dict(id=session.id))


@api.route(
    "/update_exercise_session",
    methods=["POST"],
)
@with_session
def update_exercise_session():
    form = request.form
    id = int(request.form.get("id", ""))
    duration = int(request.form.get("duration", 0))

    session = UserExerciseSession.find_by_id(id)
    session.duration = duration
    db_session.add(session)
    db_session.commit()

    return json_result(dict(id=session.id, duration=session.duration))


@api.route(
    "/get_exercise_session/<id>",
    methods=["GET"],
)
@with_session
def get_exercise_session(id):
    session = UserExerciseSession.find_by_id(id)

    return json_result(dict(id=session.id, duration=session.duration))
