import flask
from flask import request

from . import api, db_session
from zeeguu.api.utils import requires_session, json_result
from .helpers.activity_sessions import update_activity_session
from zeeguu.core.model.user_reading_session import UserReadingSession
from datetime import datetime


@api.route(
    "/reading_session_start",
    methods=["POST"],
)
@requires_session
def reading_session_start():
    article_id = int(request.form.get("article_id", ""))
    session = UserReadingSession(flask.g.user_id, article_id, datetime.now())
    db_session.add(session)
    db_session.commit()
    return json_result(dict(id=session.id))


@api.route(
    "/reading_session_update",
    methods=["POST"],
)
@requires_session
def reading_session_update():
    session = update_activity_session(UserReadingSession, request, db_session)
    return json_result(dict(id=session.id, duration=session.duration))


@api.route(
    "/reading_session_end",
    methods=["POST"],
)
@requires_session
def reading_session_end():
    session = update_activity_session(UserReadingSession, request, db_session)
    return "OK"


@api.route(
    "/reading_session_info/<id>",
    methods=["GET"],
)
@requires_session
def reading_session_info(id):
    reading_session = UserReadingSession.find_by_id(id)

    return json_result(dict(id=reading_session.id, duration=reading_session.duration))
