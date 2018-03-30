from datetime import datetime

import flask
from flask import request

from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from . import api
import zeeguu
from zeeguu.model import User, Cohort, UserActivityData, Session
import sqlalchemy
from flask import jsonify
import json
import random
import datetime

# class function wrapper
def class_function_checker(class_id):
    from zeeguu.model import TeacherCohortMap
    link = TeacherCohortMap.query.filter_by(cohort_id=class_id).all()
    for l in link:
        if l.user_id == flask.g.user.id:
            return True
    return False


# Takes user_id and returns user.name that corresponds
@api.route("/get_user_name/<id>", methods=["GET"])
@with_session
def get_user_name(id):
    user = User.query.filter_by(id=id).one()
    return user.name


# Checks to see if user has a valid active session
@api.route("/has_session", methods=["GET"])
def has_session():
    try:
        session_id = int(flask.request.args['session'])
        session = Session.query.filter_by(id=session_id).one()
        if session is None:
            print("no session exists")
            return jsonify(0)

        return jsonify(1)
    except:
        print("exception called")
        return jsonify(0)


# Checks to see if user has permissions to access a certain class.
@api.route("/get_class_permissions/<id>", methods=["GET"])
@with_session
def get_class_permissions(id):
    if(class_function_checker(id)):
        return jsonify(1)
    return jsonify(0)

@api.route("/get_user_permissions/<id>", methods=["GET"])
@with_session
def get_user_permissions(id):
    try:
        user = User.query.filter_by(id=id).one()
        return get_class_permissions(user.cohort_id)
    except:
        flask.abort(401)


# Asking for a nonexistant cohort will cause .one() to crash!
# Takes cohort_id and returns all users belonging to that cohort
@api.route("/get_users_from_class/<id>", methods=["GET"])
@with_session
def get_users_from_class(id):
    if(not class_function_checker(id)):
        flask.abort(401)
    c = Cohort.query.filter_by(id=id).one()
    if not c is None:
        users = User.query.filter_by(cohort_id=c.id).all()
        users_info = []
        for u in users:
            info = get_user_info(u.id)
            users_info.append(info)
        return json.dumps(users_info)


# Gets user words info
@with_session
def get_user_info(id):
    dictionary = {
        'id': str(id),
        'name': get_user_name(id),
        'reading_time': random.randint(1, 100),
        'exercises_done': random.randint(1, 100),
        'last_article': 'place holder article'
    }
    return dictionary



# Removes user from class

@api.route("/remove_class/<class_id>", methods=["POST"])
@with_session
def remove_class(class_id):
    if(not class_function_checker(class_id)):
        flask.abort(401)

    selected_cohort = Cohort.query.filter_by(id=class_id).one()

    if selected_cohort is None:
        flask.abort(400)

    if not selected_cohort.cur_students == 0:
        flask.abort(400)

    zeeguu.db.session.delete(select_cohort)

# Takes Teacher id as input and outputs list of all cohort_ids that teacher owns

@api.route("/get_classes", methods=["GET"])
@with_session
def get_classes_by_teacher_id():
    from zeeguu.model import TeacherCohortMap
    mappings = TeacherCohortMap.query.filter_by(user_id=flask.g.user.id).all()
    cohorts = []
    for m in mappings:
        info = get_class_info(m.cohort_id)
        cohorts.append(info)
    return json.dumps(cohorts)


# Takes cohort_id and reuturns dictionary with relevant class variables
@with_session
def get_class_info(id):
    c = Cohort.find(id)
    class_name = c.class_name
    inv_code = c.inv_code
    max_students = c.max_students
    cur_students = c.cur_students
    class_language_id = c.class_language_id
    d = {'id': str(id), 'class_name': class_name, 'inv_code': inv_code, 'max_students': max_students,
         'cur_students': cur_students, 'class_language_id': class_language_id, 'class_id': id}
    return d


# Takes two inputs (user_id, cohort_id) and links them other in teacher_cohort_map table.
# url input in format <user_id>/<cohort_id>
@api.route("/link_teacher_class/<user_id>/<cohort_id>", methods=["POST"])
def link_teacher_class(user_id, cohort_id):
    from zeeguu.model import TeacherCohortMap
    user = User.find_by_id(user_id)
    cohort = Cohort.find(cohort_id)
    zeeguu.db.session.add(TeacherCohortMap(user, cohort))
    zeeguu.db.session.commit()
    return 'added teacher_class relationship'

#Checks if the inputted invite code is already in use.
@api.route("/check_invite_code/<invite_code>", methods=["GET"])
@with_session
def check_inv_code(invite_code):
    c = Cohort.query.filter_by(inv_code=invite_code).first()
    if c is None:
        return jsonify(1)
    return jsonify(0)


# creates a class in the data base. Requires form input (inv_code, class_name, class_language_id, max_students, teacher_id)
@api.route("/add_class", methods=["POST"])
@with_session
def add_class():
    from zeeguu.model import Language
    inv_code = request.form.get("inv_code")
    class_name = request.form.get("class_name")
    class_language_id = request.form.get("class_language_id")
    class_language = Language.find_or_create(class_language_id)
    teacher_id = flask.g.user.id
    max_students = request.form.get("max_students")


    # Check for mysql injections!



    ################################
    try:
        c = Cohort(inv_code, class_name, class_language, max_students)
        zeeguu.db.session.add(c)
        zeeguu.db.session.commit()
        link_teacher_class(teacher_id, c.id)
        return jsonify(1)
    except ValueError:
        print("value error")
        flask.abort(400)
    except sqlalchemy.exc.IntegrityError:
        print("integ error")
        flask.abort(400)


# creates user and adds them to a cohort
@api.route("/add_user_with_class", methods=['POST'])
def add_user_with_class():
    email = request.form.get("email")
    password = request.form.get("password")
    username = request.form.get("username")
    inv_code = request.form.get("inv_code")

    cohort_id = Cohort.get_id(inv_code)
    cohort = Cohort.find(cohort_id)

    if not cohort is None:
        if not password is None:
            # Checks to see if there is space, if there is it increments the cur_students variables.
            # Therefor it is essential that you ensure you add the student if this function returns true.
            # Hence it being placed after other checks.
            # However, if an exeption is caught, this error is handled.
            if cohort.request_join():
                try:
                    user = User(email, username, password)
                    user.cohort = cohort
                    zeeguu.db.session.add(user)
                    zeeguu.db.session.commit()
                    return 'user created'
                except ValueError:
                    cohort.undo_join()
                    flask.abort(400)
                except sqlalchemy.exc.IntegrityError:
                    cohort.undo_join()
                    flask.abort(400)
            return 'no more space in class!'
    return 'failed :('


#Get user bookmarks
@api.route("/get_user_stats/<id>", methods=["GET", "POST"])
@with_session
def get_user_stats(id):

    user = User.query.filter_by(id=id).one()
    if(not class_function_checker(user.cohort_id)):
        flask.abort(401)
    # True input causes function to return context too.
    return json_result(user.bookmarks_by_day(True))