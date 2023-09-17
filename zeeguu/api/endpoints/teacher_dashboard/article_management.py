import json
import uuid
from datetime import datetime

import flask
import sqlalchemy
from flask import request
from sqlalchemy.orm.exc import NoResultFound

import zeeguu.core
from zeeguu.api.utils.abort_handling import make_error
from zeeguu.core.model import Cohort, Language, Article, Url, User
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from ._only_teachers_decorator import only_teachers
from ._permissions import (
    check_permission_for_cohort,
)
from .. import api
from zeeguu.api.utils.route_wrappers import with_session

from zeeguu.core.model import db


@api.route("/send_article_to_colleague", methods=["POST"])
@with_session
@only_teachers
def send_article_to_colleague():
    """
    Send article with a colleague;
    Feature requested by Pernille and her colleagues
    """
    try:
        receiving_user = User.find(request.form.get("email"))
    except sqlalchemy.orm.exc.NoResultFound:
        print("about to error: There is no user with that email")
        return make_error(401, "There is no user with that email")

    article = Article.find_by_id(request.form.get("article_id"))
    new_id = Article.create_clone(db.session, article, receiving_user)
    print(f"send email confirmation to {receiving_user} ")
    from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

    mail = ZeeguuMailer(
        f"Shared: {article.title}",
        f"Dear {receiving_user.name},\n\n"
        + f'{flask.g.user.name} shared "{article.title}" with you.\n\n'
        + f"You can find it on the My Texts page, or at the link below:\n\n"
        + f"\t https://zeeguu.org/teacher/texts/editText/{new_id}\n\n"
        + "Cheers,\n"
        + "The Zeeguu Team",
        receiving_user.email,
    )
    mail.send()
    print("email sent")

    return "OK"


@api.route("/add_article_to_cohort", methods=["POST"])
@with_session
@only_teachers
def add_article_to_cohort():
    """
    Gets all the articles of this teacher
    """

    cohort = Cohort.find(request.form.get("cohort_id"))

    check_permission_for_cohort(cohort.id)

    article = Article.find_by_id(request.form.get("article_id"))

    if not CohortArticleMap.find(cohort.id, article.id):
        now = datetime.now()
        new_mapping = CohortArticleMap(cohort, article, now)
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
    check_permission_for_cohort(cohort_id)

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
            now = datetime.now()
            new_cohort_article_map = CohortArticleMap(cohort, new_article, now)

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

    check_permission_for_cohort(cohort.id)

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

    check_permission_for_cohort(cohort_id)

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
    check_permission_for_cohort(cohort_id)

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
