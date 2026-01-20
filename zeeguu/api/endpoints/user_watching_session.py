from datetime import datetime
import flask
from flask import request

from zeeguu.api.endpoints.helpers.activity_sessions import update_activity_session
from zeeguu.api.utils import json_result, requires_session
from zeeguu.core.model.user_watching_session import UserWatchingSession

from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/watching_session_start", methods=["POST"])
# ---------------------------------------------------------------------------
@requires_session
def watching_session_start():
    video_id = int(request.form.get("video_id", ""))
    platform = request.form.get("platform", None)
    if platform is not None:
        platform = int(platform)
    session = UserWatchingSession(flask.g.user_id, video_id, datetime.now(), platform)
    db_session.add(session)
    db_session.commit()
    return json_result(dict(id=session.id))


# ---------------------------------------------------------------------------
@api.route("/watching_session_update", methods=["POST"])
# ---------------------------------------------------------------------------
@requires_session
def watching_session_update():
    session = update_activity_session(UserWatchingSession, request, db_session)
    return json_result(dict(id=session.id, duration=session.duration))
