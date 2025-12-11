import flask
from flask import request

from . import api, db_session
from zeeguu.api.utils import requires_session, json_result
from .helpers.activity_sessions import update_activity_session
from ...core.model import UserBrowsingSession


@api.route(
    "/browsing_session_start",
    methods=["POST"],
)
@requires_session
def browsing_session_start():
    session = UserBrowsingSession._create_new_session(db_session, flask.g.user_id)
    return json_result(dict(id=session.id))


@api.route(
    "/browsing_session_update",
    methods=["POST"],
)
@requires_session
def browsing_session_update():
    session = update_activity_session(UserBrowsingSession, request, db_session)
    return json_result(dict(id=session.id, duration=session.duration))


@api.route(
    "/browsing_session_end",
    methods=["POST"],
)
@requires_session
def browsing_session_end():
    session = update_activity_session(UserBrowsingSession, request, db_session)
    session.is_active = False
    db_session.add(session)
    db_session.commit()
    return "OK"


@api.route(
    "/browsing_session_info/<id>",
    methods=["GET"],
)
@requires_session
def browsing_session_info(id):
    browsing_session = UserBrowsingSession.find_by_id(id)
    return json_result(browsing_session.to_json())
