"""Where newcomers drop out of onboarding, and what happened when they did.

Most of the funnel happens before there is an account, so unlike
/upload_user_activity_data this endpoint takes no session. A session is used
when one comes along, to tie the funnel to the user it turned into.

See OnboardingFunnelEvent for what is and isn't stored.
"""

import json
import re

import flask

from zeeguu.api.utils.route_wrappers import cross_domain
from zeeguu.core.constants import PLATFORM_NAMES
from zeeguu.core.model.onboarding_funnel_event import OnboardingFunnelEvent
from zeeguu.core.model.session import Session
from zeeguu.core.util.user_agent import parse_user_agent
from . import api, db_session

# The client names the steps, so a new one needs no API deploy; this only
# keeps out what isn't shaped like a step name.
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FUNNEL_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")

# Enough for "which field, which rule, how many seconds"; anything larger is
# not what the detail is for.
MAX_DETAIL_CHARS = 1000


def _short(value, length):
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:length]


def _viewport(value):
    """Rounded to tens of pixels: exact sizes add to a fingerprint and say
    nothing more about whether the form fit on screen."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return int(min(max(round(value, -1), 0), 10000))


def _user_id_from_session():
    session_uuid = flask.request.args.get("session") or flask.request.cookies.get(
        "chocolatechip"
    )
    if not session_uuid:
        return None
    session = Session.find(session_uuid)
    return session.user_id if session else None


# ---------------------------------------------------------------------------
@api.route("/onboarding_funnel_event", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
def onboarding_funnel_event():
    """
    Record one step of a newcomer's way in. A JSON body:

        funnel_id    random id the client keeps in local storage (required)
        step         e.g. "account_form_shown" (required)
        detail       small object, e.g. {"field": "email", "rule": "taken"}
        entry_point  e.g. "landing", "shared_article", "invite", "app"
        platform, app_version, device_model, viewport_w, viewport_h,
        ui_language, online

    OS and browser come from the User-Agent header, not from the body.
    Parsed with force=True so the client can send it with navigator.sendBeacon,
    which can't set a JSON content type, as the page is closed.
    """
    body = flask.request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        return "Expected a JSON object", 400

    funnel_id = body.get("funnel_id")
    step = body.get("step")
    if not isinstance(funnel_id, str) or not _FUNNEL_ID.match(funnel_id):
        return "Bad funnel_id", 400
    if not isinstance(step, str) or not _NAME.match(step):
        return "Bad step", 400

    detail = body.get("detail")
    if detail is not None:
        if not isinstance(detail, dict) or len(json.dumps(detail)) > MAX_DETAIL_CHARS:
            return "Bad detail", 400

    entry_point = body.get("entry_point")
    if entry_point is not None and (
        not isinstance(entry_point, str) or not _NAME.match(entry_point)
    ):
        return "Bad entry_point", 400

    platform = body.get("platform")
    if platform not in PLATFORM_NAMES:
        platform = None

    online = body.get("online")
    user_id = _user_id_from_session()

    event = OnboardingFunnelEvent(
        funnel_id=funnel_id,
        user_id=user_id,
        step=step,
        detail=detail,
        entry_point=entry_point,
        platform=platform,
        app_version=_short(body.get("app_version"), 32),
        device_model=_short(body.get("device_model"), 64),
        viewport_w=_viewport(body.get("viewport_w")),
        viewport_h=_viewport(body.get("viewport_h")),
        ui_language=_short(body.get("ui_language"), 16),
        online=online if isinstance(online, bool) else None,
        **parse_user_agent(flask.request.headers.get("User-Agent")),
    )
    db_session.add(event)
    if user_id:
        OnboardingFunnelEvent.claim_funnel(funnel_id, user_id)
    db_session.commit()

    return "OK"
