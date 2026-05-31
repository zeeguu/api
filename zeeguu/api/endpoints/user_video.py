import flask
from flask import request
from zeeguu.core.model import User, UserVideo, Video
from zeeguu.core.model.caption_translation_set import (
    CaptionTranslationSet,
    STATUS_READY,
)

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/user_video", methods=("GET",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_user_video():
    video_id = request.args.get("video_id", "")
    if not video_id:
        flask.abort(400)

    video_id = int(video_id)

    print("Video ID: ", video_id)
    video = Video.find_by_id(video_id)
    user = User.find_by_id(flask.g.user_id)
    new_user_video = UserVideo.find_or_create(db_session, user, video)

    # Optional translated-caption track. If the set isn't ready yet (still translating, errored,
    # or doesn't belong to this video) we silently serve the original captions — the reader
    # polls the dedicated status endpoint and re-fetches when ready, so the worst UX is a
    # one-cycle delay rather than a 4xx during a known-async wait.
    translation_set = None
    caption_set_id = request.args.get("caption_set_id")
    if caption_set_id:
        candidate = CaptionTranslationSet.find_by_id(int(caption_set_id))
        if (
            candidate
            and candidate.video_id == video.id
            and candidate.status == STATUS_READY
        ):
            translation_set = candidate

    return json_result(
        new_user_video.user_video_info(
            user, video, with_content=True, translation_set=translation_set
        )
    )


# ---------------------------------------------------------------------------
@api.route("/video_opened", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def video_opened():
    video_id = int(request.form.get("video_id"))

    video = Video.find_by_id(video_id)
    user = User.find_by_id(flask.g.user_id)
    user_video = UserVideo.find_or_create(db_session, user, video)
    user_video.set_opened()

    db_session.add(user_video)
    db_session.commit()

    return "OK"


# ---------------------------------------------------------------------------
@api.route("/video_set_playback", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def video_set_playback():
    video_id = int(request.form.get("video_id"))
    playback_position = int(request.form.get("playback_position"))  # in milliseconds

    video = Video.find_by_id(video_id)
    user = User.find_by_id(flask.g.user_id)
    user_video = UserVideo.find_or_create(db_session, user, video)

    user_video.set_playback_position(playback_position)

    db_session.add(user_video)
    db_session.commit()

    return "OK"
