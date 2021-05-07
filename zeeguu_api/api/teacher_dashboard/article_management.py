import json
import uuid
from datetime import datetime

import flask
import sqlalchemy
from flask import request
from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from zeeguu_api.api.utils.abort_handling import make_error
from zeeguu_core.model import Cohort, Language, Article, Url
from zeeguu_core.model.cohort_article_map import CohortArticleMap
from .decorator import only_teachers
from .permissions import (
    _abort_if_no_permission_for_cohort,
)
from .. import api
from ..utils.route_wrappers import with_session

db = zeeguu_core.db


@api.route("/add_article_to_cohort", methods=["POST"])
@with_session
@only_teachers
def add_article_to_cohort():
    """
    Gets all the articles of this teacher
    """

    cohort = Cohort.find(request.form.get("cohort_id"))

    _abort_if_no_permission_for_cohort(cohort.id)

    article = Article.find_by_id(request.form.get("article_id"))

    if not CohortArticleMap.find(cohort.id, article.id):
        new_mapping = CohortArticleMap(cohort, article)
        db.session.add(new_mapping)
        db.session.commit()

    return "OK"


@api.route("/upload_articles/<cohort_id>", methods=["POST"])
@with_session
@only_teachers
def upload_articles(cohort_id):
    """
    uploads articles for a cohort with input from a POST request
    """
    _abort_if_no_permission_for_cohort(cohort_id)

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


@api.route("/get_cohorts_for_article/<article_id>", methods=["GET"])
@with_session
@only_teachers
def get_cohorts_for_article(article_id):
    """
    Gets all the cohorts for this article
    """

    article = Article.find_by_id(article_id)

    return json.dumps(CohortArticleMap.get_cohorts_for_article(article))


@api.route("/delete_article_from_cohort", methods=["POST"])
@with_session
@only_teachers
def delete_article_from_cohort():
    """
    Gets all the articles of this teacher
    """

    cohort = Cohort.find(request.form.get("cohort_id"))

    _abort_if_no_permission_for_cohort(cohort.id)

    article = Article.find_by_id(request.form.get("article_id"))

    mapping = CohortArticleMap.find(cohort.id, article.id)
    if mapping:
        db.session.delete(mapping)
        db.session.commit()
        return "OK"
    else:
        return make_error(401, "That article does not belong to the cohort!")


# DEPRECATED!
@api.route("/remove_article_from_cohort/<cohort_id>/<article_id>", methods=["POST"])
@with_session
@only_teachers
def remove_article_from_cohort(cohort_id, article_id):
    """
    Removes article by article_id.
    Only works if the teacher has permission to access the class
    """

    _abort_if_no_permission_for_cohort(cohort_id)

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


@api.route("/cohort_files/<cohort_id>", methods=["GET"])
@with_session
@only_teachers
def cohort_files(cohort_id):
    """
    Gets the files associated with a cohort
    """
    _abort_if_no_permission_for_cohort(cohort_id)

    cohort = Cohort.find(cohort_id)
    articles = CohortArticleMap.get_articles_info_for_cohort(cohort)
    return json.dumps(articles)


@api.route("/teacher_texts", methods=["GET"])
@with_session
@only_teachers
def teacher_texts():
    """
    Gets all the articles of this teacher
    """

    articles = Article.own_texts_for_user(flask.g.user)
    article_info_dicts = [article.article_info_for_teacher() for article in articles]

    return json.dumps(article_info_dicts)
