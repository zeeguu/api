import flask
import sqlalchemy
from flask import request

from zeeguu.core.model.article import Article
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from zeeguu.core.model.language import Language
from zeeguu.core.model.user import User
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.personal_copy import PersonalCopy

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from . import api, db_session


@api.route("/upload_own_text", methods=["POST"])
@cross_domain
@requires_session
def upload_own_text():

    db_session.rollback()
    language = Language.find_or_create(request.form.get("language", ""))
    content = request.form.get("content", "")
    htmlContent = request.form.get("htmlContent", "")
    title = request.form.get("title", "")
    user = User.find_by_id(flask.g.user_id)
    new_article_id = Article.create_from_upload(
        db_session, title, content, htmlContent, user, language
    )

    return str(new_article_id)


@api.route("/own_texts", methods=["GET"])
@cross_domain
@requires_session
def own_texts():
    user = User.find_by_id(flask.g.user_id)
    r = Article.own_texts_for_user(user)
    r2 = PersonalCopy.all_for(user)
    all_articles = r + r2
    all_articles.sort(key=lambda art: art.id, reverse=True)

    article_infos = [UserArticle.user_article_info(user, e) for e in all_articles]

    return json_result(article_infos)


@api.route("/delete_own_text/<id>", methods=["GET"])
@cross_domain
@requires_session
def delete_own_text(id):

    try:
        a = Article.query.filter(Article.id == id).one()
        a.deleted = 1
        db_session.commit()

        CohortArticleMap.delete_all_for_article(db_session, id)

        return "OK"

    except sqlalchemy.orm.exc.NoResultFound:
        return "An article with that ID does not exist."


@api.route("/update_own_text/<article_id>", methods=["POST"])
@cross_domain
@requires_session
def update_own_text(article_id):

    language = Language.find_or_create(request.form.get("language", ""))
    content = request.form.get("content", "")
    title = request.form.get("title", "")
    htmlContent = request.form.get("htmlContent", "")

    a = Article.query.filter(Article.id == article_id).one()
    a.update(db_session, language, content, htmlContent, title)

    db_session.add(a)
    db_session.commit()

    return "OK"
