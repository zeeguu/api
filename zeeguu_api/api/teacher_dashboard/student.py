from datetime import timedelta

from dateutil.utils import today
from flask import jsonify, request

import zeeguu_core
from zeeguu_core.model import User, Cohort
from ._common_api_parameters import (
    _get_student_cohort_and_period_from_POST_params,
)
from ._only_teachers_decorator import only_teachers
from .helpers import student_info_for_teacher_dashboard
from ._permissions import (
    check_permission_for_cohort,
    check_permission_for_user,
)
from .. import api, json_result, with_session

db = zeeguu_core.db


@api.route("/basic_user_info/<id>", methods=["GET"])
@with_session
def basic_user_info(id):

    user = check_permission_for_user(id)

    return jsonify(
        {"name": user.name, "email": user.email, "cohort_id": user.cohort_id}
    )


@api.route("/user_info", methods=["POST"])
@with_session
def user_info_api():

    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()
    check_permission_for_user(user.id)

    return jsonify(student_info_for_teacher_dashboard(user, cohort, from_date, to_date))


@api.route("/cohort_member_bookmarks", methods=["POST"])
@with_session
@only_teachers
def cohort_member_bookmarks():

    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params(
        to_string=False
    )

    check_permission_for_cohort(user.cohort_id)

    # True input causes function to return context too.
    return json_result(
        user.bookmarks_by_day(
            True, from_date, with_title=True, max=10000, language_id=cohort.language_id
        )
    )


# DEPRECATED: Use the POST instead
@api.route("/cohort_member_bookmarks/<id>/<time_period>", methods=["GET"])
@with_session
@only_teachers
def cohort_member_bookmarks_deprecated(id, time_period):

    user = User.query.filter_by(id=id).one()

    check_permission_for_cohort(user.cohort_id)

    now = today()
    date = now - timedelta(days=int(time_period))

    cohort_language_id = Cohort.query.filter_by(id=user.cohort_id).one().language_id

    # True input causes function to return context too.
    return json_result(
        user.bookmarks_by_day(
            True, date, with_title=True, max=10000, language_id=cohort_language_id
        )
    )


# DEPRECATED: Use the POST instead
@api.route("/user_info/<id>/<duration>", methods=["GET"])
@with_session
def deprecated_user_info_api(id, duration):

    check_permission_for_user(id)

    return jsonify(student_info_for_teacher_dashboard(id, duration))
