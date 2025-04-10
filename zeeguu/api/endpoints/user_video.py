import flask
from flask import request
from zeeguu.core.model import User, UserVideo, Video

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session

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
    
    print('Video ID: ', video_id)
    video = Video.query.filter_by(id=video_id).one()
    user = User.find_by_id(flask.g.user_id)
    user_video = UserVideo.find_or_create(db_session, user, video)

    return json_result(user_video.user_video_info(user, video, with_content=True))
