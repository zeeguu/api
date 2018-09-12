from datetime import datetime

import flask
from flask import request

from tests_zeeguu.rules.bookmark_rule import BookmarkRule
from zeeguu.util.timer_logging_decorator import time_this
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from . import api, db_session


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
def top_bookmarks(count):
    """
    Returns a list of the words that the user is currently studying.
    """
    top_bookmarks = flask.g.user.top_bookmarks(count)
    json_bookmarks = [b.json_serializable_dict(True) for b in top_bookmarks]
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
    after_date = datetime.strptime(after_date_string, '%Y-%m-%dT%H:%M:%S')

    return json_result(flask.g.user.bookmarks_by_day(with_context, after_date, with_title=with_title))


@api.route("/bookmarks_for_article/<article_id>", methods=["POST"])
@cross_domain
@with_session
def bookmarks_for_article(article_id):
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
    after_date = datetime.strptime(after_date_string, '%Y-%m-%dT%H:%M:%S')

    return json_result(flask.g.user.bookmarks_for_article(article_id, with_context, after_date, with_title=with_title))


@api.route("/create_default_exercises", methods=["GET"])
@cross_domain
@with_session
@time_this
def create_default_exercises():
    for _ in range(5):
        b = BookmarkRule(flask.g.user).bookmark
        db_session.add(b)
        db_session.commit()

    return "OK"
