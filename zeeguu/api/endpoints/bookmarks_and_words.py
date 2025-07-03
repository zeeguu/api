from datetime import datetime

import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User, Article, Bookmark, ExerciseSource, ExerciseOutcome
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from . import api, db_session
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.parse_json_boolean import parse_json_boolean
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.word_scheduling import BasicSRSchedule


@api.route("/user_words", methods=["GET"])
@cross_domain
@requires_session
def studied_words():
    """
    Returns a list of the words that the user is currently studying.
    """
    user = User.find_by_id(flask.g.user_id)
    return json_result(user.user_words())


@api.route("/learned_bookmarks/<int:count>", methods=["GET"])
@cross_domain
@requires_session
def learned_bookmarks(count):
    """
    Returns a list of the words that the user has learned.
    """
    user = User.find_by_id(flask.g.user_id)
    top_bookmarks = user.learned_bookmarks(count)
    json_bookmarks = [b.as_dictionary(with_exercise_info=True) for b in top_bookmarks]
    return json_result(json_bookmarks)


@api.route("/total_learned_bookmarks", methods=["GET"])
@cross_domain
@requires_session
def total_learned_bookmarks():
    """
    Returns a list of the words that the user has learned.
    """
    user = User.find_by_id(flask.g.user_id)
    total_bookmarks_learned = user.total_learned_bookmarks()
    return json_result(total_bookmarks_learned)


@api.route("/starred_bookmarks/<int:count>", methods=["GET"])
@cross_domain
@requires_session
def starred_bookmarks(count):
    """
    Returns a list of the words that the user is currently studying.
    """
    user = User.find_by_id(flask.g.user_id)
    top_bookmarks = user.starred_bookmarks(count)
    json_bookmarks = [b.as_dictionary() for b in top_bookmarks]
    return json_result(json_bookmarks)


@api.route("/bookmarks_by_day", methods=["POST"])
@cross_domain
@requires_session
def bookmarks_by_day():
    """
    Returns the bookmarks of this user organized by date. Based on the
    POST arguments, it can return also the context of the bookmark as
    well as it can return only the bookmarks after a given date.

    :param (POST) with_context: If this parameter is "true", the endpoint
    also returns the text where the bookmark was found.
    """

    with_context = parse_json_boolean(request.form.get("with_context", "false"))
    user = User.find_by_id(flask.g.user_id)
    return json_result(user.bookmarks_by_day(with_context=with_context))


@api.route("/bookmarks_for_article/<int:article_id>/<int:user_id>", methods=["POST"])
@cross_domain
@requires_session
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
        article_id, with_exercise_info=True, with_title=True
    )

    return json_result(dict(bookmarks=bookmarks, article_title=article.title))


@api.route(
    "/bookmarks_to_study_for_article/<int:article_id>",
    methods=["POST", "GET"],
)
@cross_domain
@requires_session
def bookmarks_to_study_for_article(article_id):
    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_tokens", "false"))

    bookmarks = user.bookmarks_for_article(
        article_id,
        with_exercise_info=True,
        with_title=True,
        good_for_study=True,
        with_tokens=with_tokens,
        json=True,
    )

    return json_result(bookmarks)


@api.route("/bookmarks_for_article/<int:article_id>", methods=["POST", "GET"])
@cross_domain
@requires_session
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
    return bookmarks_for_article(article_id, flask.g.user_id)


@api.route("/delete_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def delete_bookmark(bookmark_id):
    try:
        bookmark = Bookmark.find(bookmark_id)
        user_word = bookmark.user_word
        
        # Find all other bookmarks for this user_word
        other_bookmarks = (
            Bookmark.query
            .filter(Bookmark.user_word_id == user_word.id)
            .filter(Bookmark.id != bookmark.id)
            .all()
        )
        
        # If this bookmark is the preferred one, we need to handle it
        if user_word.preferred_bookmark_id == bookmark.id:
            if other_bookmarks:
                # Filter for quality bookmarks (fit_for_study)
                from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study
                quality_bookmarks = [b for b in other_bookmarks if fit_for_study(b)]
                
                if quality_bookmarks:
                    # Set the most recent quality bookmark as preferred
                    new_preferred = max(quality_bookmarks, key=lambda b: b.time)
                    user_word.preferred_bookmark = new_preferred
                    db_session.add(user_word)
                else:
                    # No quality bookmarks left, delete all remaining bookmarks and the user_word
                    for b in other_bookmarks:
                        db_session.delete(b)
                    db_session.delete(user_word)
            else:
                # No other bookmarks exist, delete the user_word
                db_session.delete(user_word)
        
        db_session.delete(bookmark)
        db_session.commit()
    except NoResultFound:
        return "Inexistent"

    return "OK"


@api.route("/report_correct_mini_exercise/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def report_learned_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.user_word.report_exercise_outcome(
        db_session,
        ExerciseSource.TOP_BOOKMARKS_MINI_EXERCISE,
        ExerciseOutcome.CORRECT,
        -1,
        db_session,
    )

    return "OK"


@api.route("/use_in_exercises/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def set_user_word_exercise_preference(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.user_preference = UserWordExPreference.USE_IN_EXERCISES
    bookmark.update_fit_for_study()
    db_session.commit()
    return "OK"


@api.route("/dont_use_in_exercises/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def set_user_word_exercise_dislike(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    user_word = bookmark.user_word
    user_word.user_preference = UserWordExPreference.DONT_USE_IN_EXERCISES
    user_word.update_fit_for_study()

    BasicSRSchedule.clear_user_word_schedule(db_session, user_word)
    db_session.commit()
    return "OK"


@api.route("/is_fit_for_study/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def set_is_fit_for_study(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.fit_for_study = True
    db_session.commit()
    return "OK"


@api.route("/not_fit_for_study/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def set_not_fit_for_study(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.fit_for_study = False

    BasicSRSchedule.clear_user_word_schedule(db_session, bookmark)
    db_session.commit()
    return "OK"


@api.route("/star_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def star_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = True
    bookmark.update_fit_for_study()
    db_session.commit()
    return "OK"


@api.route("/unstar_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def unstar_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = False
    bookmark.update_fit_for_study()
    db_session.commit()
    return "OK"


@api.route("/practiced_user_word_count_this_week", methods=["GET"])
@cross_domain
@requires_session
def practiced_user_word_count_this_week():
    """
    Returns the number of user words that the user has practiced this week.
    """
    user = User.find_by_id(flask.g.user_id)
    count = user.practiced_user_words_count_this_week()
    return json_result(count)
