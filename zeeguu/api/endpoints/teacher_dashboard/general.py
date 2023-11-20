import json


import flask

from ._only_teachers_decorator import only_teachers
from .helpers import all_user_info_from_cohort

from ._permissions import (
    has_permission_for_cohort,
    is_teacher,
    check_permission_for_user,
)


from zeeguu.api.utils.route_wrappers import with_session
from .. import api

import zeeguu.core
from zeeguu.core.model import Cohort


from zeeguu.core.model import db


@api.route("/is_teacher", methods=["GET"])
@with_session
def is_teacher_api():
    return str(is_teacher(flask.g.user.id))


@api.route("/has_permission_for_cohort/<id>", methods=["GET"])
@with_session
@only_teachers
def has_permission_for_cohort_api(id):

    if has_permission_for_cohort(id):
        return "OK"
    return "Denied"


@api.route("/has_permission_for_user_info/<id>", methods=["GET"])
@with_session
@only_teachers
def has_permission_for_user_info(id):

    check_permission_for_user(id)

    return "OK"


@api.route("/users_by_teacher/<duration>", methods=["GET"])
@with_session
@only_teachers
def users_by_teacher(duration):
    """
    Return list of dictionaries containing
    user info for all users in cohorts that the logged in user owns.
    """

    from zeeguu.core.model import TeacherCohortMap

    mappings = TeacherCohortMap.query.filter_by(user_id=flask.g.user.id).all()
    all_users = []
    for m in mappings:
        users = all_user_info_from_cohort(m.cohort_id, duration)
        all_users.extend(users)
    return json.dumps(all_users)


@api.route("/invite_code_usable/<invite_code>", methods=["GET"])
@with_session
@only_teachers
def inv_code_usable(invite_code):
    """
    Checks if the inputted invite code is already in use.

    """
    c = Cohort.query.filter_by(inv_code=invite_code).first()
    if c is None:
        return "OK"
    return "False"
