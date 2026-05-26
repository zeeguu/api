"""Endpoint for sharing a single video to Zeeguu for interactive viewing.

Mirrors article_upload, but for video. The client (browser extension / iOS WKWebView)
extracts the captions from YouTube's authorized player and hands them to us, sidestepping
the server-side caption fetch that YouTube blocks from datacenter IPs. We fetch only
metadata (via the Data API key, which is key-authenticated and not IP-blocked) and create
the Video + Caption rows, then the client opens the existing /user_video reader.
"""
import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User, Language
from zeeguu.core.model.video import Video
from zeeguu.core.youtube_api.youtube_api import extract_youtube_video_id
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session

from . import api, db_session


def _payload():
    """Read fields from a JSON body, falling back to form for scalars."""
    data = request.get_json(silent=True) or {}

    def field(name):
        value = data.get(name)
        if value is None:
            value = request.form.get(name)
        return value

    return data, field


@api.route("/video_upload/create", methods=["POST"])
@cross_domain
@requires_session
def video_upload_create():
    user = User.find_by_id(flask.g.user_id)

    data, field = _payload()

    video_unique_key = (field("video_unique_key") or "").strip()
    if not video_unique_key:
        video_unique_key = extract_youtube_video_id(field("url") or "")
    if not video_unique_key:
        flask.abort(400, "A YouTube url or video_unique_key is required")

    lang_code = (field("language") or "").strip()
    if not lang_code:
        flask.abort(400, "language required")
    try:
        Language.find(lang_code)
    except NoResultFound:
        flask.abort(406, "Language not supported")

    # Captions extracted client-side: list of {time_start, time_end, text} (times in ms).
    # Optional — if absent we fall through to broken=NO_CAPTIONS and report it below.
    captions = data.get("captions")

    video = Video.find_or_create(
        db_session,
        video_unique_key,
        lang_code,
        captions=captions,
        enforce_language=False,
        enforce_caption_length=False,
    )

    if video is None:
        flask.abort(422, "Could not fetch video info from YouTube")
    if video.broken != 0:
        # 1=no captions, 5=missing duration. The client should surface a friendly
        # "this video has no subtitles yet" for the no-captions case.
        flask.abort(422, f"Video not usable for interactive viewing (code {video.broken})")

    return json_result(
        {"video_id": video.id, "video_unique_key": video.video_unique_key}
    )
