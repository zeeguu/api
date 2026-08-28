import flask
from flask import request
from zeeguu.api.utils import json_result

from zeeguu.core.model import Cohort, User

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session


# ---------------------------------------------------------------------------
@api.route("/join_cohort", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def join_cohort_api():
    invite_code = request.form.get("invite_code", "")

    if not invite_code:
        flask.abort(400)

    try:
        cohort = Cohort.find_by_code(invite_code)
        user = User.find_by_id(flask.g.user_id)
        user.add_user_to_cohort(cohort, db_session)

        return "OK"

    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        flask.abort(500)


@api.route("/student_info", methods=["GET"])
@cross_domain
@requires_session
def student_info():
    from zeeguu.core.model import Cohort

    user = User.find_by_id(flask.g.user_id)

    # The classroom feed only shows texts in the language the student is
    # currently learning, so a class in another language looks empty and
    # unexplained. Ship the per-language counts alongside each class: they are
    # what lets the empty classroom name the language and offer the switch.
    # One query for every class, not one per class -- Leaderboards and
    # MyClassrooms call this endpoint too and never read the counts.
    cohorts = [c.cohort for c in user.cohorts]
    counts = Cohort.text_counts_by_language_for([c.id for c in cohorts])

    user_cohorts = []
    for cohort in cohorts:
        info = cohort.get_cohort_info()
        info["texts_by_language"] = counts.get(cohort.id, [])
        user_cohorts.append(info)

    return json_result(
        {
            "name": user.name,
            "email": user.email,
            "learned_language": (
                user.learned_language.code if user.learned_language else None
            ),
            "cohorts": user_cohorts,
        }
    )


@api.route("/cohort_name/<id>", methods=["GET"])
@requires_session
def cohort_name(id):

    cohort = Cohort.find(id)
    return {"name": cohort.name}
