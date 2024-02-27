import json

import flask
import sqlalchemy
from flask import request, jsonify
from sqlalchemy.orm.exc import NoResultFound

import zeeguu.core
from zeeguu.core.model import (
    User,
    Cohort,
    Language,
    TeacherCohortMap,
    CohortArticleMap,
    Teacher,
)
from zeeguu.core.model.user_reading_session import UserReadingSession
from ._common_api_parameters import _convert_number_of_days_to_date_interval
from ._only_teachers_decorator import only_teachers
from .helpers import (
    all_user_info_from_cohort,
    get_cohort_info,
)
from ._permissions import (
    check_permission_for_cohort,
    check_permission_for_user,
)
from .. import api
from zeeguu.api.utils.route_wrappers import with_session

from zeeguu.core.model import db


@api.route("/remove_cohort/<cohort_id>", methods=["POST"])
@with_session
def remove_cohort(cohort_id):
    """
    Removes cohort by cohort_id.
    Can only be called successfully if the class is empty.

    """
    from zeeguu.core.model import TeacherCohortMap

    check_permission_for_cohort(cohort_id)

    try:
        selected_cohort = Cohort.query.filter_by(id=cohort_id).one()

        for student in selected_cohort.get_students():
            student.cohort_id = None
            db.session.add(student)

        links = TeacherCohortMap.query.filter_by(cohort_id=cohort_id).all()
        for link in links:
            db.session.delete(link)

        CohortArticleMap.delete_all_for_cohort(db.session, cohort_id)

        db.session.delete(selected_cohort)
        db.session.commit()
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/create_own_cohort", methods=["POST"])
@with_session
@only_teachers
def create_own_cohort():
    """
    Creates a cohort in the database.
    Requires form input (inv_code, name, language_id, max_students, teacher_id)

    """

    def _link_teacher_cohort(user_id, cohort_id):
        """
        Takes user_id and cohort_id and links them together in teacher_cohort_map table.
        """
        from zeeguu.core.model import TeacherCohortMap

        user = User.find_by_id(user_id)
        cohort = Cohort.find(cohort_id)
        db.session.add(TeacherCohortMap(user, cohort))
        db.session.commit()
        return "added teacher_cohort relationship"

    params = request.form
    inv_code = params.get("inv_code")
    name = params.get("name")

    # language_id is deprecated and kept here for backwards compatibility
    # use language_code instead
    language_code = params.get("language_code") or params.get("language_id")
    if name is None or inv_code is None or language_code is None:
        flask.abort(400)

    available_languages = Language.available_languages()
    code_allowed = False
    for code in available_languages:
        if language_code in str(code):
            code_allowed = True

    if not code_allowed:
        flask.abort(400)
    language = Language.find_or_create(language_code)
    teacher_id = flask.g.user.id
    max_students = params.get("max_students")
    if int(max_students) < 1:
        flask.abort(400)

    try:
        c = Cohort(inv_code, name, language, max_students)
        db.session.add(c)
        db.session.commit()
        _link_teacher_cohort(teacher_id, c.id)
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
        return "IntegrityError"


@api.route("/update_cohort/<cohort_id>", methods=["POST"])
@with_session
@only_teachers
def update_cohort(cohort_id):
    """
    changes details of a specified cohort.
    requires input form (inv_code, name, max_students)

    """
    check_permission_for_cohort(cohort_id)

    try:
        params = request.form

        cohort_to_change = Cohort.query.filter_by(id=cohort_id).one()
        cohort_to_change.inv_code = params.get("inv_code")
        cohort_to_change.name = params.get("name")

        # language_id is deprecated; use language_code instead
        language_code = params.get("language_code") or params.get("language_id")
        cohort_to_change.language_id = Language.find(language_code).id

        cohort_to_change.declared_level_min = params.get("declared_level_min")
        cohort_to_change.declared_level_max = params.get("declared_level_max")

        db.session.commit()
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
        return "IntegrityError"


@api.route("/users_from_cohort/<id>/<duration>", methods=["GET"])
@with_session
def users_from_cohort(id, duration):
    """
    Takes id for a cohort and returns all users belonging to that cohort.
    """
    check_permission_for_cohort(id)

    from_date, to_date = _convert_number_of_days_to_date_interval(
        duration, to_string=True
    )
    try:
        users_info = all_user_info_from_cohort(id, from_date, to_date)

        return json.dumps(users_info)
    except KeyError:
        flask.abort(400)
        return "KeyError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/cohorts_info", methods=["GET"])
@with_session
@only_teachers
def cohorts_info():
    """
    Return list of dictionaries containing cohort info for all cohorts that the logged in user owns.

    """

    mappings = TeacherCohortMap.query.filter_by(user_id=flask.g.user.id).all()
    cohorts = []
    for m in mappings:
        info = get_cohort_info(m.cohort_id)
        cohorts.append(info)
    return json.dumps(cohorts)


@api.route("/cohort_info/<id>", methods=["GET"])
@with_session
@only_teachers
def wrapper_to_json_class(id):
    """
    Takes id of cohort and then wraps _get_cohort_info
    returns jsonified result of _get_cohort_info
    """
    check_permission_for_cohort(id)

    return jsonify(get_cohort_info(id))


@api.route("/add_colleague_to_cohort", methods=["POST"])
@with_session
@only_teachers
def add_colleague_to_cohort():
    cohort_id = request.form.get("cohort_id")
    colleague_email = request.form.get("colleague_email")

    check_permission_for_cohort(cohort_id)

    colleague = User.find(colleague_email)
    cohort = Cohort.find(cohort_id)

    if not Teacher.exists(colleague):
        teacher = Teacher(colleague)
        db.session.add(teacher)
        db.session.commit()

    db.session.add(TeacherCohortMap(colleague, cohort))
    db.session.commit()

    return "OK"


@api.route("/remove_user_from_cohort/<user_id>", methods=["GET"])
@with_session
@only_teachers
def remove_user_from_cohort(user_id):
    check_permission_for_user(user_id)

    u = User.find_by_id(user_id)
    u.cohort_id = None
    db.session.add(u)
    db.session.commit()

    return "OK"
