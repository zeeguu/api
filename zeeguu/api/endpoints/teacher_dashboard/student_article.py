import flask
from sqlalchemy import func
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import Article, Cohort, User
from zeeguu.core.model.db import db
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_reading_session import UserReadingSession
from ._permissions import check_permission_for_user
from .. import api
from zeeguu.api.utils import json_result, requires_session


@api.route("/student_article/<int:article_id>", methods=["GET"])
@requires_session
def student_article(article_id):
    """
    An article as a student left it: its text with *the student's*
    translations as past bookmarks, so their teacher sees where they needed
    help, in place. Read-only for the teacher: nothing is logged.

    Also, for the header that says whose reading this is:
    student_reading_seconds, the time the student spent on it over every
    session (a reread counts), beside the reading_completion it already has.

    Query params: student_id, cohort_id.
    """
    try:
        cohort = Cohort.find(flask.request.args["cohort_id"])
        student = User.query.filter_by(id=flask.request.args["student_id"]).one()
    except (KeyError, NoResultFound):
        flask.abort(400)
    check_permission_for_user(student.id, cohort.id)

    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404)
    info = UserArticle.user_article_info(student, article, with_content=True)
    milliseconds = (
        db.session.query(func.sum(UserReadingSession.duration))
        .filter_by(user_id=student.id, article_id=article.id)
        .scalar()
    )
    info["student_reading_seconds"] = round((milliseconds or 0) / 1000)
    return json_result(info)
