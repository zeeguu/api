import json
from datetime import datetime, timedelta

import flask
from flask import request, jsonify

import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound

import uuid

from .utils.json_result import json_result
from .utils.route_wrappers import with_session
from . import api

import zeeguu_core
from zeeguu_core.model import User, Cohort, Language, Teacher, Article, Url
from zeeguu_core.model.cohort_article_map import CohortArticleMap

db = zeeguu_core.db


def _is_teacher(user_id):
    try:
        Teacher.query.filter_by(user_id=user_id).one()
        return True
    except NoResultFound:

        return False


@api.route("/is_teacher", methods=["GET"])
@with_session
def is_teacher():
    return str(_is_teacher(flask.g.user.id))


def has_permission_for_cohort(cohort_id):
    '''

        Checks to see if user requesting has permissions to view the cohort with id 'cohort_id'

    '''
    from zeeguu_core.model import TeacherCohortMap
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


def user_info_from_cohort(id, duration):
    '''
       Takes id for a cohort and returns all users belonging to that cohort.
    '''
    c = Cohort.query.filter_by(id=id).one()
    users = User.query.filter_by(cohort_id=c.id).all()
    users_info = []
    for u in users:
        info = _get_user_info_for_teacher_dashboard(u.id, duration)
        users_info.append(info)
    return users_info


@api.route("/users_from_cohort/<id>/<duration>", methods=["GET"])
@with_session
def users_from_cohort(id, duration):
    '''
        Takes id for a cohort and returns all users belonging to that cohort.

    '''
    if (not has_permission_for_cohort(id)):
        flask.abort(401)
    try:
        users_info = user_info_from_cohort(id, duration)
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
        Takes id for a user and wraps _get_user_info
        then returns result jsonified.

    '''
    if (not has_permission_for_user_info(id) == "OK"):
        flask.abort(401)
    return jsonify(_get_user_info_for_teacher_dashboard(id, duration))


def _get_user_info_for_teacher_dashboard(id, duration):
    from zeeguu_core.model import UserReadingSession, UserExerciseSession

    '''
        Takes id for a cohort and returns a dictionary with id,name,email,reading_time,exercises_done and last article

    '''
    try:
        fromDate = datetime.now() - timedelta(days=int(duration))

        reading_sessions = UserReadingSession.find_by_user(
            int(id), fromDate, datetime.now())

        exercise_sessions = UserExerciseSession.find_by_user(
            int(id), fromDate, datetime.now())

        user = User.query.filter_by(id=id).one()

        reading_time_list = list()
        exercise_time_list = list()
        reading_time = 0
        exercise_time = 0
        for n in range(0, int(duration) + 1):
            reading_time_list.append(0)
            exercise_time_list.append(0)

        for each in reading_sessions:
            startDay = each.start_time.date()
            index = (datetime.now().date() - startDay).days
            reading_time_list[index] += each.duration / 1000
            reading_time += each.duration / 1000

        for j in exercise_sessions:
            startDay = j.start_time.date()
            index = (datetime.now().date() - startDay).days
            exercise_time_list[index] += j.duration / 1000
            exercise_time += j.duration / 1000

        dictionary = {
            'id': str(id),
            'name': user.name,
            'cohort_name': user.cohort.name,
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
    from zeeguu_core.model import TeacherCohortMap
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
    from zeeguu_core.model import TeacherCohortMap
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

        try:
            language_id = c.language_id
            language = Language.query.filter_by(id=language_id).one()
            language_name = language.name

        except ValueError:
            language_name = "None"
        except sqlalchemy.orm.exc.NoResultFound:
            language_name = "None"
        dictionary = {'id': str(id), 'name': name, 'inv_code': inv_code, 'max_students': max_students,
                      'cur_students': cur_students, 'language_name': language_name,
                      'declared_level_min': c.declared_level_min, 'declared_level_max': c.declared_level_max}
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
    from zeeguu_core.model import TeacherCohortMap
    user = User.find_by_id(user_id)
    cohort = Cohort.find(cohort_id)
    db.session.add(TeacherCohortMap(user, cohort))
    db.session.commit()
    return 'added teacher_cohort relationship'

@api.route("/users_by_teacher/<duration>", methods=["GET"])
@with_session
def users_by_teacher(duration):
    '''
        Return list of dictionaries containing user info for all cohorts that the logged in user owns.

    '''

    from zeeguu_core.model import TeacherCohortMap
    mappings = TeacherCohortMap.query.filter_by(user_id=flask.g.user.id).all()
    all_users = []
    for m in mappings:
        users = user_info_from_cohort(m.cohort_id, duration)
        all_users.extend(users)
    return json.dumps(all_users)

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
        Creates a cohort in the database.
        Requires form input (inv_code, name, language_id, max_students, teacher_id)

    '''

    if not _is_teacher(flask.g.user.id):
        flask.abort(401)

    inv_code = request.form.get("inv_code")
    name = request.form.get("name")
    language_id = request.form.get("language_id")
    if name is None or inv_code is None or language_id is None:
        flask.abort(400)
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


@api.route("/add_teacher/<id>", methods=['POST'])
def add_teacher(id):
    try:
        user = User.query.filter_by(id=id).one()
        teacher = Teacher(user)
        db.session.add(teacher)
        db.session.commit()
        return "OK"
    except:
        flask.abort(400)


@api.route("/cohort_member_reading_sessions/<id>/<time_period>", methods=["GET"])
@with_session
def cohort_member_reading_sessions(id, time_period):
    '''
        Returns reading sessions from member with input user id.
    '''
    try:
        user = User.query.filter_by(id=id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoUserFound"

    if (not has_permission_for_cohort(user.cohort_id)):
        flask.abort(401)

    now = datetime.today()
    date = now - timedelta(days=int(time_period))
    return json_result(user.reading_sessions_by_day(date, max=10000))


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
    date = now - timedelta(days=int(time_period))

    # True input causes function to return context too.
    return json_result(user.bookmarks_by_day(True, date, with_title=True, max=10000))


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

        cohort_to_change.declared_level_min = request.form.get(
            "declared_level_min")
        cohort_to_change.declared_level_max = request.form.get(
            "declared_level_max")

        db.session.commit()
        return 'OK'
    except ValueError:
        flask.abort(400)
        return 'ValueError'
    except sqlalchemy.exc.IntegrityError:
        flask.abort(400)
        return 'IntegrityError'


@api.route("/upload_articles/<cohort_id>", methods=["POST"])
@with_session
def upload_articles(cohort_id):
    '''
        uploads articles for a cohort with input from a POST request
    '''
    if (not has_permission_for_cohort(cohort_id)):
        flask.abort(401)
    try:
        for article_data in json.loads(request.data):
            url = Url('userarticle/{}'.format(uuid.uuid4().hex))
            title = article_data['title']
            authors = article_data['authors']
            content = article_data['content']
            summary = article_data['summary']
            published_time = datetime.now()
            language_code = article_data['language_code']
            language = Language.find(language_code)

            new_article = Article(
                url,
                title,
                authors,
                content,
                summary,
                published_time,
                None,  # rss feed
                language
            )
            
            db.session.add(new_article)
            db.session.flush()
            db.session.refresh(new_article)
            
            cohort = Cohort.find(cohort_id)
            new_cohort_article_map = CohortArticleMap(cohort, new_article)

            db.session.add(new_cohort_article_map)
        db.session.commit()
        return 'OK'
    except ValueError:
        flask.abort(400)
        return 'ValueError'


@api.route("/cohort_files/<cohort_id>", methods=["GET"])
@with_session
def cohort_files(cohort_id):
    '''
        Gets the files associated with a cohort
    '''
    cohort = Cohort.find(cohort_id) 
    articles = CohortArticleMap.get_articles_info_for_cohort(cohort)
    return json.dumps(articles)

@api.route("/remove_article_from_cohort/<cohort_id>/<article_id>", methods=["POST"])
@with_session
def remove_article_from_cohort(cohort_id, article_id):
    '''
        Removes article by article_id.
        Only works if the teacher has permission to access the class
    '''

    if (not has_permission_for_cohort(cohort_id)):
      flask.abort(401)
    try:
      article_in_class = CohortArticleMap.query.filter_by(article_id=article_id).one()
      db.session.delete(article_in_class)
      db.session.commit()
      return 'OK'
    except ValueError:
      flask.abort(400)
      return 'ValueError'
    except sqlalchemy.orm.exc.NoResultFound:
      flask.abort(400)
      return "NoResultFound"
