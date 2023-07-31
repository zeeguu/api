from datetime import timedelta, datetime

import flask
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.api.endpoints.teacher_dashboard._permissions import check_permission_for_user
from zeeguu.core.model import User, Cohort
from zeeguu.core.sql.query_building import date_format, datetime_format


def _convert_number_of_days_to_date_interval(number_of_days, to_string=True):

    to_date = datetime.now()
    from_date = to_date - timedelta(days=int(number_of_days))

    if to_string:
        then_str = date_format(from_date)
        now_str = datetime_format(to_date)

        return then_str, now_str

    return from_date, to_date


def _get_student_cohort_and_period_from_POST_params(
    to_string=True,
):
    student_id = flask.request.form.get("student_id")
    number_of_days = flask.request.form.get("number_of_days")
    cohort_id = flask.request.form.get("cohort_id")

    try:
        user = User.query.filter_by(id=student_id).one()
        cohort = Cohort.find(cohort_id)
    except NoResultFound:
        flask.abort(400)

    check_permission_for_user(user.id)

    from_date, to_date = _convert_number_of_days_to_date_interval(
        number_of_days, to_string
    )

    return user, cohort, from_date, to_date
