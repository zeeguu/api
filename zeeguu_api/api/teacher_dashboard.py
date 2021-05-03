import json
from datetime import datetime, timedelta

import flask
from flask import request, jsonify

import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound

import uuid

from zeeguu_api.api.utils.abort_handling import make_error
from zeeguu_core.model.student import Student

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
    """

    Checks to see if user requesting has permissions to view the cohort with id 'cohort_id'

    """
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
    if has_permission_for_cohort(id):
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
    """
    Takes id for a cohort and returns all users belonging to that cohort.
    """
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
    """
    Takes id for a cohort and returns all users belonging to that cohort.

    """
    if not has_permission_for_cohort(id):
        flask.abort(401)
    try:
        users_info = user_info_from_cohort(id, duration)
        if flask.g.user.id in [2362]:
            from faker import Faker

            for each in users_info:
                each["name"] = Faker().name()

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
    """
    Takes id for a user and wraps _get_user_info
    then returns result jsonified.

    """
    if not has_permission_for_user_info(id) == "OK":
        flask.abort(401)
    return jsonify(_get_user_info_for_teacher_dashboard(id, duration))


def _get_user_info_for_teacher_dashboard(id, duration):
    """
    Takes id for a cohort and returns a dictionary with
    id,name,email,reading_time,exercises_done and last article

    """
    try:

        student = Student(id)
        return student.info_for_teacher_dashboard(duration)

    except ValueError:
        flask.abort(400)
        return "ValueError"


@api.route("/remove_cohort/<cohort_id>", methods=["POST"])
@with_session
def remove_cohort(cohort_id):
    """
    Removes cohort by cohort_id.
    Can only be called successfully if the class is empty.

    """
    from zeeguu_core.model import TeacherCohortMap

    if not has_permission_for_cohort(cohort_id):
        flask.abort(401)
    try:
        selected_cohort = Cohort.query.filter_by(id=cohort_id).one()

        for student in selected_cohort.get_students():
            student.cohort_id = None
            db.session.add(student)

        links = TeacherCohortMap.query.filter_by(cohort_id=cohort_id).all()
        for link in links:
            db.session.delete(link)
        db.session.delete(selected_cohort)
        db.session.commit()
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/cohorts_info", methods=["GET"])
@with_session
def cohorts_by_ownID():
    """
    Return list of dictionaries containing cohort info for all cohorts that the logged in user owns.

    """
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
    """
    Takes id of cohort and then wraps _get_cohort_info
    returns jsonified result of _get_cohort_info
    """
    if not has_permission_for_cohort(id):
        flask.abort(401)
    return jsonify(_get_cohort_info(id))


def _get_cohort_info(id):
    """
    Takes id of cohort and returns dictionary with id, name, inv_code, max_students, cur_students and language_name
    """
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
        dictionary = {
            "id": str(id),
            "name": name,
            "inv_code": inv_code,
            "max_students": max_students,
            "cur_students": cur_students,
            "language_name": language_name,
            "declared_level_min": c.declared_level_min,
            "declared_level_max": c.declared_level_max,
        }
        return dictionary
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


def _link_teacher_cohort(user_id, cohort_id):
    """
    Takes user_id and cohort_id and links them together in teacher_cohort_map table.
    """
    from zeeguu_core.model import TeacherCohortMap

    user = User.find_by_id(user_id)
    cohort = Cohort.find(cohort_id)
    db.session.add(TeacherCohortMap(user, cohort))
    db.session.commit()
    return "added teacher_cohort relationship"


@api.route("/users_by_teacher/<duration>", methods=["GET"])
@with_session
def users_by_teacher(duration):
    """
    Return list of dictionaries containing user info for all cohorts that the logged in user owns.

    """

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
    """
    Checks if the inputted invite code is already in use.

    """
    c = Cohort.query.filter_by(inv_code=invite_code).first()
    if c is None:
        return "OK"
    return "False"


@api.route("/create_own_cohort", methods=["POST"])
@with_session
def create_own_cohort():
    """
    Creates a cohort in the database.
    Requires form input (inv_code, name, language_id, max_students, teacher_id)

    """

    if not _is_teacher(flask.g.user.id):
        flask.abort(401)

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


@api.route("/add_teacher/<id>", methods=["POST"])
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
    """
    Returns reading sessions from member with input user id.
    """
    try:
        user = User.query.filter_by(id=id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoUserFound"

    if not has_permission_for_cohort(user.cohort_id):
        flask.abort(401)

    cohort = Cohort.query.filter_by(id=user.cohort_id).one()
    cohort_language_id = cohort.language_id

    now = datetime.today()
    date = now - timedelta(days=int(time_period))
    return json_result(
        user.reading_sessions_by_day(date, max=10000, language_id=cohort_language_id)
    )


@api.route("/cohort_member_bookmarks/<id>/<time_period>", methods=["GET"])
@with_session
def cohort_member_bookmarks(id, time_period):
    """
    Returns books marks from member with input user id.
    """
    try:
        user = User.query.filter_by(id=id).one()
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoUserFound"

    if not has_permission_for_cohort(user.cohort_id):
        flask.abort(401)

    now = datetime.today()
    date = now - timedelta(days=int(time_period))

    cohort_language_id = Cohort.query.filter_by(id=user.cohort_id).one().language_id

    # True input causes function to return context too.
    return json_result(
        user.bookmarks_by_day(
            True, date, with_title=True, max=10000, language_id=cohort_language_id
        )
    )


@api.route("/update_cohort/<cohort_id>", methods=["POST"])
@with_session
def update_cohort(cohort_id):
    """
    changes details of a specified cohort.
    requires input form (inv_code, name, max_students)

    """
    if not has_permission_for_cohort(cohort_id):
        flask.abort(401)
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


@api.route("/upload_articles/<cohort_id>", methods=["POST"])
@with_session
def upload_articles(cohort_id):
    """
    uploads articles for a cohort with input from a POST request
    """
    if not has_permission_for_cohort(cohort_id):
        flask.abort(401)
    try:
        for article_data in json.loads(request.data):
            url = Url("userarticle/{}".format(uuid.uuid4().hex))
            title = article_data["title"]
            authors = article_data["authors"]
            content = article_data["content"]
            summary = article_data["summary"]
            published_time = datetime.now()
            language_code = article_data["language_code"]
            language = Language.find(language_code)

            new_article = Article(
                url,
                title,
                authors,
                content,
                summary,
                published_time,
                None,  # rss feed
                language,
            )

            db.session.add(new_article)
            db.session.flush()
            db.session.refresh(new_article)

            cohort = Cohort.find(cohort_id)
            new_cohort_article_map = CohortArticleMap(cohort, new_article)

            db.session.add(new_cohort_article_map)
        db.session.commit()
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"


@api.route("/cohort_files/<cohort_id>", methods=["GET"])
@with_session
def cohort_files(cohort_id):
    """
    Gets the files associated with a cohort
    """
    cohort = Cohort.find(cohort_id)
    articles = CohortArticleMap.get_articles_info_for_cohort(cohort)
    return json.dumps(articles)


# DEPRECATED!
@api.route("/remove_article_from_cohort/<cohort_id>/<article_id>", methods=["POST"])
@with_session
def remove_article_from_cohort(cohort_id, article_id):
    """
    Removes article by article_id.
    Only works if the teacher has permission to access the class
    """

    if not has_permission_for_cohort(cohort_id):
        flask.abort(401)
    try:
        article_in_class = CohortArticleMap.query.filter_by(article_id=article_id).one()
        db.session.delete(article_in_class)
        db.session.commit()
        return "OK"
    except ValueError:
        flask.abort(400)
        return "ValueError"
    except sqlalchemy.orm.exc.NoResultFound:
        flask.abort(400)
        return "NoResultFound"


@api.route("/teacher_texts", methods=["GET"])
@with_session
def teacher_texts():
    """
    Gets all the articles of this teacher
    """

    articles = Article.own_texts_for_user(flask.g.user)
    article_info_dicts = [article.article_info_for_teacher() for article in articles]

    return json.dumps(article_info_dicts)


@api.route("/get_cohorts_for_article/<article_id>", methods=["GET"])
@with_session
def get_cohorts_for_article(article_id):
    """
    Gets all the cohorts for this article
    """

    article = Article.find_by_id(article_id)

    return json.dumps(CohortArticleMap.get_cohorts_for_article(article))


@api.route("/add_article_to_cohort", methods=["POST"])
@with_session
def add_article_to_cohort():
    """
    Gets all the articles of this teacher
    """

    cohort = Cohort.find(request.form.get("cohort_id"))

    if not has_permission_for_cohort(cohort.id):
        flask.abort(401)

    article = Article.find_by_id(request.form.get("article_id"))

    if not CohortArticleMap.find(cohort.id, article.id):
        new_mapping = CohortArticleMap(cohort, article)
        db.session.add(new_mapping)
        db.session.commit()

    return "OK"


@api.route("/delete_article_from_cohort", methods=["POST"])
@with_session
def delete_article_from_cohort():
    """
    Gets all the articles of this teacher
    """

    cohort = Cohort.find(request.form.get("cohort_id"))

    if not has_permission_for_cohort(cohort.id):
        flask.abort(401)

    article = Article.find_by_id(request.form.get("article_id"))

    mapping = CohortArticleMap.find(cohort.id, article.id)
    if mapping:
        db.session.delete(mapping)
        db.session.commit()
        return "OK"
    else:
        return make_error(401, "That article does not belong to the cohort!")
