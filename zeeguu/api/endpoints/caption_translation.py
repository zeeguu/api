"""Endpoints for the per-video translated-captions feature (v1.5 of share-to-video).

POST kicks off (or returns the existing) per-(video, target_language, cefr) translation set
and runs the LLM job in a background thread; GET polls the set's status. Once `ready`, the
reader calls /user_video?caption_set_id=... to get the translated caption block.
"""
import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User, Language
from zeeguu.core.model.video import Video
from zeeguu.core.model.caption_translation_set import (
    CaptionTranslationSet,
    CEFR_LEVELS,
    STATUS_READY,
)
from zeeguu.core.llm_services.caption_translation_service import translate_set
from zeeguu.api.utils.background import run_in_background
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session

from . import api, db_session


def _resolve_video_or_404(video_id: int) -> Video:
    video = Video.find_by_id(video_id)
    if video is None:
        flask.abort(404, "video not found")
    return video


def _resolve_language_or_406(code: str) -> Language:
    try:
        return Language.find(code)
    except NoResultFound:
        flask.abort(406, "Language not supported")


def _read_body():
    data = request.get_json(silent=True) or {}
    return {
        "target_language": (data.get("target_language") or request.form.get("target_language") or "").strip(),
        "target_cefr": (data.get("target_cefr") or request.form.get("target_cefr") or "").strip().upper(),
    }


@api.route("/video/<int:video_id>/translate_captions", methods=["POST"])
@cross_domain
@requires_session
def video_translate_captions(video_id):
    User.find_by_id(flask.g.user_id)  # validates session and existence
    video = _resolve_video_or_404(video_id)

    body = _read_body()
    if not body["target_language"]:
        flask.abort(400, "target_language required")
    if body["target_cefr"] not in CEFR_LEVELS:
        flask.abort(400, f"target_cefr must be one of {CEFR_LEVELS}")
    target_language = _resolve_language_or_406(body["target_language"])

    if target_language.code == video.language.code:
        flask.abort(400, "target_language matches the video's caption language")

    # Idempotent: the second request for the same (video, language, cefr) returns the existing
    # set without re-translating. If already ready, no background job — caller polls and goes.
    translation_set = CaptionTranslationSet.find_or_create(
        db_session, video, target_language, body["target_cefr"]
    )

    if translation_set.status != STATUS_READY:
        run_in_background(translate_set, translation_set.id)

    return json_result(translation_set.as_dictionary()), 202


@api.route("/video/<int:video_id>/translate_captions/status", methods=["GET"])
@cross_domain
@requires_session
def video_translate_captions_status(video_id):
    User.find_by_id(flask.g.user_id)
    video = _resolve_video_or_404(video_id)

    set_id = request.args.get("set_id")
    if not set_id:
        flask.abort(400, "set_id required")
    translation_set = CaptionTranslationSet.find_by_id(int(set_id))
    if translation_set is None or translation_set.video_id != video.id:
        flask.abort(404, "translation set not found for this video")

    return json_result(translation_set.as_dictionary())
