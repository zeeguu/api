import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.api.utils import json_result
from zeeguu.api.utils.abort_handling import make_error

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
    except NoResultFound:
        # A 400, not the 500 this used to fall through to: the rate limiter
        # charges rejected codes only, and a code naming no class is the
        # caller's mistake, not a server error. Clients treat both as failure.
        return make_error(400, "Invalid invite code")

    # Joining a class you are already in is a no-op, not a duplicate-key 500
    # (the client shows "check the invite code" for that, so students retry).
    # Before the capacity check: a member of a full class is still a member.
    user = User.find_by_id(flask.g.user_id)
    if user.is_member_of_cohort(cohort.id):
        return "OK"

    # Same rule as signup (create_account): a full class, or one closed by
    # setting max_students to -10 as event codes are, takes nobody new. A
    # class with no max_students at all could always be joined here, and
    # still can; cohort_still_has_capacity can't do arithmetic on NULL.
    if cohort.max_students is not None and not cohort.cohort_still_has_capacity():
        return make_error(
            400, "No more places in this class. Please contact us (zeeguu.team@gmail.com)."
        )

    try:
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
    user = User.find_by_id(flask.g.user_id)

    # The classroom feed only shows texts in the language the student is
    # currently learning, so a class in another language looks empty and
    # unexplained. Ship the per-language counts alongside each class: they are
    # what lets the empty classroom name the language and offer the switch.
    user_cohorts = []
    for c in user.cohorts:
        info = c.cohort.get_cohort_info()
        info["texts_by_language"] = c.cohort.text_counts_by_language()
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
