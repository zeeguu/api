import flask
from flask import request

from . import api, db_session
from zeeguu.api.utils import requires_session, json_result
from .helpers.activity_sessions import update_activity_session
from ...core.model import UserListeningSession


@api.route(
    "/listening_session_start",
    methods=["POST"],
)
@requires_session
def listening_session_start():
    daily_audio_lesson_id = int(request.form.get("lesson_id", ""))
    session = UserListeningSession._create_new_session(
        db_session, flask.g.user_id, daily_audio_lesson_id
    )
    return json_result(dict(id=session.id))


@api.route(
    "/listening_session_update",
    methods=["POST"],
)
@requires_session
def listening_session_update():
    session = update_activity_session(UserListeningSession, request, db_session)
    return json_result(dict(id=session.id, duration=session.duration))


@api.route(
    "/listening_session_end",
    methods=["POST"],
)
@requires_session
def listening_session_end():
    session = update_activity_session(UserListeningSession, request, db_session)
    session.is_active = False
    db_session.add(session)
    db_session.commit()
    return "OK"


@api.route(
    "/listening_session_info/<id>",
    methods=["GET"],
)
@requires_session
def listening_session_info(id):
    listening_session = UserListeningSession.find_by_id(id)
    return json_result(listening_session.to_json())
