from datetime import datetime

import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.bookmark_quality import top_bookmarks
from zeeguu.core.model import User, Article, Bookmark, ExerciseSource, ExerciseOutcome
from . import api, db_session
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, with_session


@api.route("/user_words", methods=["GET"])
@cross_domain
@with_session
def studied_words():
    """
    Returns a list of the words that the user is currently studying.
    """
    return json_result(flask.g.user.user_words())


@api.route("/top_bookmarks/<int:count>", methods=["GET"])
@cross_domain
@with_session
def top_bookmarks_route(count):
    """
    Returns a list of the words that the user is currently studying.
    """
    bookmarks = top_bookmarks(flask.g.user, count)
    json_bookmarks = [b.json_serializable_dict(True) for b in bookmarks]
    return json_result(json_bookmarks)


@api.route("/learned_bookmarks/<int:count>", methods=["GET"])
@cross_domain
@with_session
def learned_bookmarks(count):
    """
    Returns a list of the words that the user is currently studying.
    """
    top_bookmarks = flask.g.user.learned_bookmarks(count)
    json_bookmarks = [b.json_serializable_dict(True) for b in top_bookmarks]
    return json_result(json_bookmarks)


@api.route("/starred_bookmarks/<int:count>", methods=["GET"])
@cross_domain
@with_session
def starred_bookmarks(count):
    """
    Returns a list of the words that the user is currently studying.
    """
    top_bookmarks = flask.g.user.starred_bookmarks(count)
    json_bookmarks = [b.json_serializable_dict(True) for b in top_bookmarks]
    return json_result(json_bookmarks)


@api.route("/bookmarks_by_day/<return_context>", methods=["GET"])
@cross_domain
@with_session
def get_bookmarks_by_day(return_context):
    """
    Returns the bookmarks of this user organized by date
    :param return_context: If "with_context" it also returns the
    text where the bookmark was found. If <return_context>
    is anything else, the context is not returned.

    """
    with_context = return_context == "with_context"
    return json_result(flask.g.user.bookmarks_by_day(with_context))


@api.route("/bookmarks_by_day", methods=["POST"])
@cross_domain
@with_session
def post_bookmarks_by_day():
    """
    Returns the bookmarks of this user organized by date. Based on the
    POST arguments, it can return also the context of the bookmark as
    well as it can return only the bookmarks after a given date.

    :param (POST) with_context: If this parameter is "true", the endpoint
    also returns the text where the bookmark was found.

    :param (POST) after_date: the date after which to start retrieving
     the bookmarks. if no date is specified, all the bookmarks are returned.
     The date format is: %Y-%m-%dT%H:%M:%S. E.g. 2001-01-01T01:55:00

    """
    with_context = request.form.get("with_context", "false") in ["True", "true"]
    with_title = request.form.get("with_title", "false") in ["True", "true"]
    after_date_string = request.form.get("after_date", "1970-01-01T00:00:00")
    after_date = datetime.strptime(after_date_string, "%Y-%m-%dT%H:%M:%S")

    return json_result(
        flask.g.user.bookmarks_by_day(with_context, after_date, with_title=with_title)
    )


@api.route("/bookmarks_for_article/<int:article_id>/<int:user_id>", methods=["POST"])
@cross_domain
@with_session
def bookmarks_for_article(article_id, user_id):
    """
    Returns the bookmarks of this user organized by date. Based on the
    POST arguments, it can return also the context of the bookmark as
    well as it can return only the bookmarks after a given date.

    :param (POST) with_context: If this parameter is "true", the endpoint
    also returns the text where the bookmark was found.

    :param (POST) after_date: the date after which to start retrieving
     the bookmarks. if no date is specified, all the bookmarks are returned.
     The date format is: %Y-%m-%dT%H:%M:%S. E.g. 2001-01-01T01:55:00

    """

    user = User.find_by_id(user_id)
    article = Article.query.filter_by(id=article_id).one()

    bookmarks = user.bookmarks_for_article(
        article_id, with_context=True, with_title=True
    )

    return json_result(dict(bookmarks=bookmarks, article_title=article.title))


@api.route("/bookmarks_to_study_for_article/<int:article_id>", methods=["POST", "GET"])
@cross_domain
@with_session
def bookmarks_to_study_for_article(article_id):

    user = User.find_by_id(flask.g.user.id)
    article = Article.query.filter_by(id=article_id).one()

    bookmarks = user.bookmarks_for_article(
        article_id, with_context=True, with_title=True, good_for_study=True
    )

    return json_result(dict(bookmarks=bookmarks, article_title=article.title))


@api.route("/bookmarks_for_article/<int:article_id>", methods=["POST", "GET"])
@cross_domain
@with_session
def bookmarks_for_article_2(article_id):
    """
    Returns the bookmarks of this user organized by date. Based on the
    POST arguments, it can return also the context of the bookmark as
    well as it can return only the bookmarks after a given date.

    :param (POST) with_context: If this parameter is "true", the endpoint
    also returns the text where the bookmark was found.

    :param (POST) after_date: the date after which to start retrieving
     the bookmarks. if no date is specified, all the bookmarks are returned.
     The date format is: %Y-%m-%dT%H:%M:%S. E.g. 2001-01-01T01:55:00

    """

    return bookmarks_for_article(article_id, flask.g.user.id)


@api.route("/delete_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def delete_bookmark(bookmark_id):
    try:
        bookmark = Bookmark.find(bookmark_id)
        db_session.delete(bookmark)
        db_session.commit()
    except NoResultFound:
        return "Inexistent"

    return "OK"


@api.route("/report_correct_mini_exercise/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def report_learned_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.report_exercise_outcome(
        ExerciseSource.TOP_BOOKMARKS_MINI_EXERCISE,
        ExerciseOutcome.CORRECT,
        -1,
        db_session,
    )

    return "OK"


@api.route("/star_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def star_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = True
    bookmark.update_fit_for_study()
    db_session.commit()
    return "OK"


@api.route("/unstar_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def unstar_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = False
    bookmark.update_fit_for_study()
    db_session.commit()
    return "OK"
