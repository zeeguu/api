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
from datetime import datetime, timedelta

db = zeeguu.db


def has_permission_for_cohort(cohort_id):
    '''
        Checks to see if user requesting has permissions to view the cohort with id 'cohort_id'
    '''
    from zeeguu.model import TeacherCohortMap
    maps = TeacherCohortMap.query.filter_by(cohort_id=cohort_id).all()
    for m in maps:
        if m.user_id == flask.g.user.id:
            return True
    return False


@api.route("/has_permission_for_cohort/<id>", methods=["GET"])
@with_session
def has_permission_for_cohort_public(id):
    """

        Checks to see if user has permissions to access a certain class.

    """
    if (has_permission_for_cohort(id)):
        return "OK"
    return "Denied"


@api.route("/has_permission_for_user_info/<id>", methods=["GET"])
@with_session
def has_permission_for_user_info(id):
    """

        Checks to see if user has permissions to access a certain user.

    """
    try:
        user = User.query.filter_by(id=id).one()
        return has_permission_for_cohort_public(user.cohort_id)
    except KeyError:
        flask.abort(400)
        return "KeyError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/users_from_cohort/<id>/<duration>", methods=["GET"])
@with_session
def users_from_cohort(id, duration):
    '''
        Takes id for a cohort and returns all users belonging to that cohort.

    '''
    if (not has_permission_for_cohort(id)):
        flask.abort(401)
    try:
        c = Cohort.query.filter_by(id=id).one()
        users = User.query.filter_by(cohort_id=c.id).all()
        users_info = []
        for u in users:
            info = _get_user_info(u.id, duration)
            users_info.append(info)
        return json.dumps(users_info)
    except KeyError:
        flask.abort(400)
        return "KeyError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/user_info/<id>/<duration>", methods=["GET"])
@with_session
def wrapper_to_json_user(id, duration):
    '''
        Takes id for a cohort and wraps _get_user_info
        then returns result jsonified.

    '''
    if (not has_permission_for_user_info(id) == "OK"):
        flask.abort(401)
    return jsonify(_get_user_info(id, duration))


def _get_user_info(id, duration):
    from zeeguu.model import UserReadingSession, UserExerciseSession

    '''
        Takes id for a cohort and returns a dictionary with id,name,email,reading_time,exercises_done and last article

    '''
    try:
        fromDate = datetime.now() - timedelta(days=int(duration))

        times1 = UserReadingSession.find_by_user(id, fromDate, datetime.now())


        times2 = UserExerciseSession.find_by_user(id, fromDate, datetime.now())


        user = User.query.filter_by(id=id).one()

        reading_time_list = list()
        exercise_time_list = list()
        reading_time = 0
        exercise_time = 0
        for n in range(0,int(duration)):
            reading_time_list[n] = 0;
            exercise_time_list[n] =0;

        for i in times1:
            startDay = i.start_time
            print("startDay = " +startDay)
            index = (datetime.now()-startDay).day
            print("Chose index =" + index)
            reading_time_list[index] += i.duration/1000
            reading_time += i.duration/1000;

        for j in times2:
            startDay = i.start_time
            index = (datetime.now() - startDay).day
            exercise_time_list[index] += i.duration/1000
            exercise_time += i.duration/1000;




        dictionary = {
            'id': str(id),
            'name': user.name,
            'email': user.email,
            'reading_time': reading_time,
            'exercises_done': exercise_time,
            'last_article': 'place holder article',
            'reading_time_list': reading_time_list,
            'exercise_time_list': exercise_time_list
        }
        return dictionary
    except ValueError:
        flask.abort(400)
        return 'ValueError'


@api.route("/remove_cohort/<cohort_id>", methods=["POST"])
@with_session
def remove_cohort(cohort_id):
    '''
        Removes cohort by cohort_id.
        Can only be called successfuly if the class is empty.

    '''
    from zeeguu.model import TeacherCohortMap
    if (not has_permission_for_cohort(cohort_id)):
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
        return 'OK'
    except ValueError:
        flask.abort(400)
        return 'ValueError'
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/cohorts_info", methods=["GET"])
@with_session
def cohorts_by_ownID():
    '''
        Return list of dictionaries containing cohort info for all cohorts that the logged in user owns.

    '''
    from zeeguu.model import TeacherCohortMap
    mappings = TeacherCohortMap.query.filter_by(user_id=flask.g.user.id).all()
    cohorts = []
    for m in mappings:
        info = _get_cohort_info(m.cohort_id)
        cohorts.append(info)
    return json.dumps(cohorts)


@api.route("/cohort_info/<id>", methods=["GET"])
@with_session
def wrapper_to_json_class(id):
    '''
        Takes id of cohort and then wraps _get_cohort_info
        returns jsonified result of _get_cohort_info
    '''
    if (not has_permission_for_cohort(id)):
        flask.abort(401)
    return jsonify(_get_cohort_info(id))


def _get_cohort_info(id):
    '''
        Takes id of cohort and returns dictionary with id, name, inv_code, max_students, cur_students and language_name
    '''
    try:
        c = Cohort.find(id)
        name = c.name
        inv_code = c.inv_code
        max_students = c.max_students
        cur_students = c.get_current_student_count()
        language_id = c.language_id
        language = Language.query.filter_by(id=language_id).one()
        dictionary = {'id': str(id), 'name': name, 'inv_code': inv_code, 'max_students': max_students,
                      'cur_students': cur_students, 'language_name': language.name}
        return dictionary
    except ValueError:
        flask.abort(400)
        return 'ValueError'
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


def _link_teacher_cohort(user_id, cohort_id):
    '''
        Takes user_id and cohort_id and links them together in teacher_cohort_map table.
    '''
    from zeeguu.model import TeacherCohortMap
    user = User.find_by_id(user_id)
    cohort = Cohort.find(cohort_id)
    db.session.add(TeacherCohortMap(user, cohort))
    db.session.commit()
    return 'added teacher_cohort relationship'


@api.route("/invite_code_usable/<invite_code>", methods=["GET"])
@with_session
def inv_code_usable(invite_code):
    '''
        Checks if the inputted invite code is already in use.

    '''
    c = Cohort.query.filter_by(inv_code=invite_code).first()
    if c is None:
        return "OK"
    return "False"


@api.route("/create_own_cohort", methods=["POST"])
@with_session
def create_own_cohort():
    '''
        Creates a class in the database.
        Requires form input (inv_code, name, language_id, max_students, teacher_id)

    '''
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
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
        return "IntegrityError"


@api.route("/add_user_with_cohort", methods=['POST'])
def add_user_with_cohort():
    '''
        Creates user and adds them to a cohort
        Requires input form (email, password, username, inv_code)

    '''
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


@api.route("/cohort_member_bookmarks/<id>/<time_period>", methods=["GET"])
@with_session
def cohort_member_bookmarks(id, time_period):
    '''
        Returns books marks from member with input user id.
    '''
    try:
        user = User.query.filter_by(id=id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoUserFound"

    if (not has_permission_for_cohort(user.cohort_id)):
        flask.abort(401)

    now = datetime.today()
    date = now - timedelta(days=int(time_period));

    # True input causes function to return context too.
    return json_result(user.bookmarks_by_day(True, date))


@api.route("/update_cohort/<cohort_id>", methods=["POST"])
@with_session
def update_cohort(cohort_id):
    '''
        changes details of a specified cohort.
        requires input form (inv_code, name, max_students)

    '''
    if (not has_permission_for_cohort(cohort_id)):
        flask.abort(401)
    try:
        cohort_to_change = Cohort.query.filter_by(id=cohort_id).one()
        cohort_to_change.inv_code = request.form.get("inv_code")
        cohort_to_change.name = request.form.get("name")

        if int(request.form.get("max_students")) < 1:
            flask.abort(400)

        cohort_to_change.max_students = request.form.get("max_students")

        db.session.commit()
        return 'OK'
    except ValueError:
        flask.abort(400)
        return 'ValueError'
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
        return 'IntegrityError'


