import flask
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import Article, Cohort, User
from zeeguu.core.model.user_article import UserArticle
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
    return json_result(UserArticle.user_article_info(student, article, with_content=True))
