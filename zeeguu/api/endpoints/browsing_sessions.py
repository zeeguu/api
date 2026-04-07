import flask
from flask import request

from . import api, db_session
from zeeguu.api.utils import requires_session, json_result
from zeeguu.api.utils.route_wrappers import cross_domain
from .helpers.activity_sessions import update_activity_session
from ...core.model import User, UserBrowsingSession


@api.route(
    "/browsing_session_start",
    methods=["POST"],
)
@cross_domain
@requires_session
def browsing_session_start():
    platform = request.form.get("platform", None)
    if platform is not None:
        platform = int(platform)
    # Capture the user's current learned_language so streak attribution
    # survives a later language toggle (see activity_sessions._session_language).
    user = User.find_by_id(flask.g.user_id)
    language_id = user.learned_language_id if user else None
    session = UserBrowsingSession._create_new_session(
        db_session, flask.g.user_id, platform=platform, language_id=language_id
    )
    return json_result(dict(id=session.id))


@api.route(
    "/browsing_session_update",
    methods=["POST"],
)
@cross_domain
@requires_session
def browsing_session_update():
    session = update_activity_session(UserBrowsingSession, request, db_session)
    return json_result(dict(id=session.id, duration=session.duration))


@api.route(
    "/browsing_session_end",
    methods=["POST"],
)
@cross_domain
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
@cross_domain
@requires_session
def browsing_session_info(id):
    browsing_session = UserBrowsingSession.find_by_id(id)
    return json_result(browsing_session.to_json())
