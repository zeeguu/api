import flask
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User, Cohort
from zeeguu.core.user_statistics.session_history import session_history
from ._permissions import check_permission_for_cohort, check_permission_for_user
from ..session_history import date_range_from_request
from .. import api
from zeeguu.api.utils import json_result, requires_session


@api.route("/student_session_history", methods=["GET"])
@requires_session
def student_session_history():
    """
    A student's Activity -> History, as their teacher sees it: only the
    class's language, with every translated word's full sentence and whether
    the student practised it.

    Query params: student_id, cohort_id, and either from_date + to_date (ISO)
    or days.
    """
    try:
        cohort = Cohort.find(flask.request.args["cohort_id"])
        student = User.query.filter_by(id=flask.request.args["student_id"]).one()
    except (KeyError, NoResultFound):
        flask.abort(400)

    check_permission_for_cohort(cohort.id)
    check_permission_for_user(student.id, cohort.id)

    from_date, to_date = date_range_from_request()
    return json_result(
        session_history(
            student.id, cohort.language_id, from_date, to_date, for_teacher=True
        )
    )
