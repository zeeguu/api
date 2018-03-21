from datetime import datetime

import flask
from flask import request

from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from . import api
import zeeguu
from zeeguu.model import User, Cohort, UserActivityData
import sqlalchemy
# Using jsonify here to return a list with flask.
from flask import jsonify
import random



#class function wrapper
#def class_function_wrapper(class_id, teacher_id):

#    link = TeacherCohortMap.query.filter_by(teacher_id=user.id).all()
    #for id in link.cohort_id
    #    if(id == class_id):
    #        return True
    #flask.abort(401)
#    return False

#teacher function wrapper
#def teacher_function_wrapper(teacher_id):
#    session_id = int(flask.request.args['session'])
#    user = session.user
#    if(user.id == teacher_id):
#        return True
#    flask.abort(401)
#    return False


#student function wrapper
#def student_function_wrapper(student_id):
#    student = User.query.filter_by(id=student_id)
#    class_id = student.cohort_id
#    return class_function_wrapper(class_id)



#Takes user_id and returns user.name that corresponds
@api.route("/get_user_name/<id>", methods=["GET"])
def get_user_name(id):
    user = User.query.filter_by(id=id).one()
    return user.name



# Asking for a nonexistant cohort will cause .one() to crash!
# Takes cohort_id and returns all users belonging to that cohort
@api.route("/get_users_from_class/<id>", methods=["GET"])
def get_users_from_class(id):
    c = Cohort.query.filter_by(id=id).one()
    if not c is None:
        users = User.query.filter_by(cohort_id=c.id).all()
        ids = []
        for u in users:
            ids.append(u.id)
        return jsonify(ids)


# Takes Teacher id as input and outputs list of all cohort_ids that teacher owns
@api.route("/get_classes_by_teacher_id/<id>", methods=["GET"])
def get_classes_by_teacher_id(id):
    from zeeguu.model import TeacherCohortMap
    mappings = TeacherCohortMap.query.filter_by(user_id=id).all()
    cohort_ids = []
    for m in mappings:
        cohort_ids.append(m.cohort_id)
    return jsonify(cohort_ids)

# Takes cohort_id and reuturns dictionary with relevant class variables
@api.route("/get_class_info/<id>", methods=["GET"])
#@with_session
def get_class_info(id):
    if(True) #meant to be class_function_wrapper
        c = Cohort.find(id)
        class_name = c.class_name
        inv_code = c.inv_code
        max_students = c.max_students
        cur_students = c.cur_students
        class_language_id = c.class_language_id
        d = {'class_name':class_name, 'inv_code':inv_code, 'max_students':max_students,'cur_students':cur_students,'class_language_id':class_language_id, 'class_id':id}
        return jsonify(d)
    return None

# Takes two inputs (user_id, cohort_id) and links them other in teacher_cohort_map table.
# url input in format <user_id>/<cohort_id>
@api.route("/link_teacher_class/<user_id>/<cohort_id>", methods=["POST"])
def link_teacher_class(user_id, cohort_id):
    from zeeguu.model import TeacherCohortMap
    user = User.find_by_id(user_id)
    cohort = Cohort.find(cohort_id)
    zeeguu.db.session.add(TeacherCohortMap(user,cohort))
    zeeguu.db.session.commit()
    return 'added teacher_class relationship'

# creates a class in the data base. Requires form input (inv_code, class_name, class_language_id, max_students, teacher_id)
@api.route("/add_class", methods=["POST"])
@with_session
def add_class():

    from zeeguu.model import Language
    inv_code = request.form.get("inv_code")
    class_name = request.form.get("class_name")
    class_language_id = request.form.get("class_language_id")
    class_language = Language.find_or_create(class_language_id)
    teacher_id = request.form.get("teacher_id")
    max_students = request.form.get("max_students")
    print("gets here")
    try:
        print("gets into try")
        c = Cohort(inv_code, class_name, class_language, max_students)
        print("created class")
        zeeguu.db.session.add(c)
        zeeguu.db.session.commit()
        print("added class to database")
        link_teacher_class(teacher_id,c.id)
        print("linked class to teacher")
        return 'added class complete.'
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


# Gets user words info
@api.route("/get_user_info/<id>", methods=['GET'])
def get_user_info(id):
    dictionary = {
        'reading_time': random.randint(1,100),
        'exercises_done': random.randint(1,100),
        'last_article': 'place holder article'
    }
    return jsonify(dictionary)

