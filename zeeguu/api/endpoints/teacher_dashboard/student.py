from datetime import timedelta

from dateutil.utils import today
from flask import jsonify

import zeeguu.core
from zeeguu.core.model import User, Cohort
from ._common_api_parameters import (
    _get_student_cohort_and_period_from_POST_params,
    _convert_number_of_days_to_date_interval,
)
from ._only_teachers_decorator import only_teachers
from ._permissions import (
    check_permission_for_cohort,
    check_permission_for_user,
)
from .helpers import student_info_for_teacher_dashboard
from zeeguu.api.utils import json_result, with_session

from .. import api


from zeeguu.core.model import db


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

    from_date, to_date = _convert_number_of_days_to_date_interval(
        duration, to_string=True
    )

    user = User.query.filter_by(id=id).one()

    return jsonify(
        student_info_for_teacher_dashboard(user, user.cohort, from_date, to_date)
    )
