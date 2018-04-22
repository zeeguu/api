from datetime import datetime

import flask
from flask import request

from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from . import api
import zeeguu
from zeeguu.model import User, Cohort, UserActivityData, Session, Language
import sqlalchemy
from flask import jsonify
import json
import random
import datetime

db = zeeguu.db


# Checked to see if the user requesting has permission to view the cohort with id 'cohort_id'
def _has_permission_for_cohort(cohort_id):
    from zeeguu.model import TeacherCohortMap
    links = TeacherCohortMap.query.filter_by(cohort_id=cohort_id).all()
    for l in links:
        if l.user_id == flask.g.user.id:
            return True
    return False


# Checks to see if user has a valid active session
@api.route("/has_session", methods=["GET"])
def has_session():
    try:
        session_id = int(flask.request.args['session'])
        session = Session.query.filter_by(id=session_id).one()
        return jsonify(1)
    except:
        return jsonify(0)


@api.route("/get_cohort_permissions/<id>", methods=["GET"])
@with_session
def get_cohort_permissions(id):
    """

        Checks to see if user has permissions to access a certain class.

    """
    if (_has_permission_for_cohort(id)):
        return jsonify(1)
    return jsonify(0)


@api.route("/get_user_permissions/<id>", methods=["GET"])
@with_session
def get_user_permissions(id):
    """

        Checks to see if user has permissions to access a certain user.

    """
    try:
        user = User.query.filter_by(id=id).one()
        return get_cohort_permissions(user.cohort_id)
    except:
        flask.abort(401)


# Asking for a nonexistant cohort will cause .one() to crash!
# Takes cohort_id and returns all users belonging to that cohort
@api.route("/get_users_from_cohort/<id>", methods=["GET"])
@with_session
def get_users_from_cohort(id):
    if (not _has_permission_for_cohort(id)):
        flask.abort(401)
    try:
        c = Cohort.query.filter_by(id=id).one()
        users = User.query.filter_by(cohort_id=c.id).all()
        users_info = []
        for u in users:
            info = _get_user_info(u.id)
            users_info.append(info)
        return json.dumps(users_info)

    except:
        flask.abort(400)


# Takes cohort_id and reuturns dictionary with relevant class variables
@api.route("/get_user_info/<id>", methods=["GET"])
@with_session
def wrapper_to_json_user(id):
    if (not get_user_permissions(id)):
        flask.abort(401)
    return jsonify(_get_user_info(id))


# Gets user info
def _get_user_info(id):
    try:
        user = User.query.filter_by(id=id).one()
        dictionary = {
            'id': str(id),
            'name': user.name,
            'email': user.email,
            'reading_time': random.randint(1, 100),
            'exercises_done': random.randint(1, 100),
            'last_article': 'place holder article'
        }
        return dictionary
    except ValueError:
        flask.abort(400)


# Removes class.Can only be called successfuly if the class is empty. Otherwise we return 400 (Value error).
@api.route("/remove_cohort/<cohort_id>", methods=["POST"])
@with_session
def remove_cohort(cohort_id):
    from zeeguu.model import TeacherCohortMap
    if (not _has_permission_for_cohort(cohort_id)):
        flask.abort(401)
    try:
        selected_cohort = Cohort.query.filter_by(id=cohort_id).one()

        if not selected_cohort.get_current_student_count() == 0:
            flask.abort(400)

        links = TeacherCohortMap.query.filter_by(cohort_id=cohort_id).all()
        for link in links:
            db.session.delete(link)
        db.session.delete(selected_cohort)
        db.session.commit()
        return 'removed'
    except ValueError:
        flask.abort(400)


# Takes Teacher id as input and outputs list of all cohort_ids that teacher owns
@api.route("/get_cohorts", methods=["GET"])
@with_session
def get_cohorts_by_ownID():
    from zeeguu.model import TeacherCohortMap
    mappings = TeacherCohortMap.query.filter_by(user_id=flask.g.user.id).all()
    cohorts = []
    for m in mappings:
        info = _get_cohort_info(m.cohort_id)
        cohorts.append(info)
    return json.dumps(cohorts)


# Takes cohort_id and reuturns dictionary with relevant class variables
@api.route("/get_cohort_info/<id>", methods=["GET"])
@with_session
def wrapper_to_json_class(id):
    if (not _has_permission_for_cohort(id)):
        flask.abort(401)
    return jsonify(_get_cohort_info(id))


def _get_cohort_info(id):
    c = Cohort.find(id)
    name = c.name
    inv_code = c.inv_code
    max_students = c.max_students
    cur_students = c.get_current_student_count()
    language_id = c.language_id
    language = Language.query.filter_by(id=language_id).one()
    d = {'id': str(id), 'name': name, 'inv_code': inv_code, 'max_students': max_students,
         'cur_students': cur_students, 'language_name': language.name, 'id': id}
    return d


# Takes two inputs (user_id, cohort_id) and links them to one another in teacher_cohort_map table.
def _link_teacher_cohort(user_id, cohort_id):
    from zeeguu.model import TeacherCohortMap
    user = User.find_by_id(user_id)
    cohort = Cohort.find(cohort_id)
    db.session.add(TeacherCohortMap(user, cohort))
    db.session.commit()
    return 'added teacher_cohort relationship'


# Checks if the inputted invite code is already in use.
@api.route("/check_invite_code/<invite_code>", methods=["GET"])
@with_session
def check_inv_code(invite_code):
    c = Cohort.query.filter_by(inv_code=invite_code).first()
    if c is None:
        return jsonify(1)
    return jsonify(0)


# creates a class in the data base. Requires form input (inv_code, name, language_id, max_students, teacher_id)
@api.route("/create_own_cohort", methods=["POST"])
@with_session
def create_own_cohort():
    inv_code = request.form.get("inv_code")
    name = request.form.get("name")
    language_id = request.form.get("language_id")
    available_languages = Language.available_languages()
    code_allowed = False
    for code in available_languages:
        if language_id in str(code):
            code_allowed = True

    if not code_allowed:
        flask.abort(400)
    language = Language.find_or_create(language_id)
    teacher_id = flask.g.user.id
    max_students = request.form.get("max_students")
    if int(max_students) < 1:
        flask.abort(400)

    try:
        c = Cohort(inv_code, name, language, max_students)
        db.session.add(c)
        db.session.commit()
        _link_teacher_cohort(teacher_id, c.id)
        return jsonify(1)
    except ValueError:
        # print("value error")
        flask.abort(400)
    except sqlalchemy.exc.IntegrityError:
        # print("integ error")
        flask.abort(400)


# creates user and adds them to a cohort
@api.route("/add_user_with_cohort", methods=['POST'])
def add_user_with_cohort():
    email = request.form.get("email")
    password = request.form.get("password")
    username = request.form.get("username")
    inv_code = request.form.get("inv_code")

    try:
        cohort_id = Cohort.get_id(inv_code)
        cohort = Cohort.find(cohort_id)
    except:
        flask.abort(400)

    if not len(password) == 0:
        # Checks to see if there is space, if there is it increments the cur_students variables.
        # Therefore it is essential that you ensure you add the student if this function returns true.
        # Hence it being placed after other checks.
        # However, if an exeption is caught, this error is handled.
        if cohort.cohort_still_has_capacity():
            try:
                user = User(email, username, password)
                user.cohort = cohort
                db.session.add(user)
                db.session.commit()
                return 'user created'
            except ValueError:
                flask.abort(400)
            except sqlalchemy.exc.IntegrityError:
                flask.abort(400)
        return 'no more space in class!'
    flask.abort(400)


# Get user bookmarks
@api.route("/get_user_bookmarks/<id>", methods=["GET", "POST"])
@with_session
def get_user_bookmarks(id):
    user = User.query.filter_by(id=id).one()
    if (not _has_permission_for_cohort(user.cohort_id)):
        flask.abort(401)
    # True input causes function to return context too.
    return json_result(user.bookmarks_by_day(True))


@api.route("/update_cohort/<cohort_id>", methods=["POST"])
@with_session
def update_cohort(cohort_id):
    if (not _has_permission_for_cohort(cohort_id)):
        flask.abort(401)
    try:
        cohort_to_change = Cohort.query.filter_by(id=cohort_id).one()
        cohort_to_change.inv_code = request.form.get("inv_code")
        cohort_to_change.name = request.form.get("name")

        if int(request.form.get("max_students")) < 1:
            flask.abort(400)

        cohort_to_change.max_students = request.form.get("max_students")

        db.session.commit()
        return 'updated'
    except ValueError:
        flask.abort(400)
        return 'failed'
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
        return 'failed'
