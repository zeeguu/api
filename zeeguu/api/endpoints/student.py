import flask
from flask import request
from zeeguu.api.utils import json_result

from zeeguu.core.model import Cohort

from zeeguu.api.utils.route_wrappers import cross_domain, with_session
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/join_cohort", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def join_cohort_api():
    invite_code = request.form.get("invite_code", "")

    if not invite_code:
        flask.abort(400)

    try:
        cohort = Cohort.find_by_code(invite_code)
        flask.g.user.cohort_id = cohort.id
        db_session.add(flask.g.user)
        db_session.commit()

        return "OK"

    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        flask.abort(500)


@api.route("/student_info", methods=["GET"])
@cross_domain
@with_session
def student_info():

    return json_result(
        {
            "name": flask.g.user.name,
            "email": flask.g.user.email,
            "cohort_id": flask.g.user.cohort_id,
        }
    )


@api.route("/cohort_name/<id>", methods=["GET"])
@with_session
def cohort_name(id):

    cohort = Cohort.find(id)
    return {"name": cohort.name}
