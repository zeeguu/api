import flask
from flask import request
from zeeguu_core.model import Cohort

from .utils.route_wrappers import cross_domain, with_session
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/join_cohort", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def join_cohort():
    invite_code = request.form.get("invite_code", "")

    if not invite_code:
        flask.abort(400)

    try:
        cohort = Cohort.find_by_code(invite_code)
        flask.g.user.cohort_id = cohort.id
        db_session.add(flask.g.user)
        db_session.commit()

        return cohort.name
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        flask.abort(500)
