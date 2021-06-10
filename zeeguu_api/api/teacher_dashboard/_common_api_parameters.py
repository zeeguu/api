from datetime import timedelta, datetime

import flask
from sqlalchemy.orm.exc import NoResultFound

from zeeguu_api.api.teacher_dashboard._permissions import check_permission_for_user
from zeeguu_core.model import User, Cohort
from zeeguu_core.sql.query_building import date_format, datetime_format


def _parse__student_id__cohort_id__and__number_of_days():
    student_id = flask.request.form.get("student_id")
    number_of_days = flask.request.form.get("number_of_days")
    cohort_id = flask.request.form.get("cohort_id")

    try:
        user = User.query.filter_by(id=student_id).one()
        cohort = Cohort.find(cohort_id)
    except NoResultFound:
        flask.abort(400)

    check_permission_for_user(user.id)

    now = datetime.now()
    then = now - timedelta(days=int(number_of_days))

    then_str = date_format(then)
    now_str = datetime_format(now)

    return user, cohort, then_str, now_str
