import flask
from flask import request
from zeeguu.core.model import User, UserVideo, Video

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api

# ---------------------------------------------------------------------------
@api.route("/user_video", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def user_video():
    video_id = request.args.get("video_id", "")
    if not video_id:
        flask.abort(400)
    
    video_id = int(video_id)
    
    print(video_id)
    video = Video.query.filter_by(id=video_id).one()
    user = User.find_by_id(flask.g.user_id)

    return json_result(UserVideo.user_video_info(user, video, with_content=True))
