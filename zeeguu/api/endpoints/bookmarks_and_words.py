from datetime import datetime

import flask
from flask import request
from sqlalchemy import or_
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model import User, Article, Bookmark, ExerciseSource, ExerciseOutcome
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
from . import api, db_session
from zeeguu.api.utils.json_result import json_result
from zeeguu.logging import log
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


@api.route("/learned_user_words/<int:count>", methods=["GET"])
@cross_domain
@requires_session
def learned_user_words(count):
    """
    Returns a list of the user words that the user has learned (deduplicated).
    Unlike learned_bookmarks which can have duplicates for the same word from different contexts,
    this endpoint returns unique learned user words.
    """
    user = User.find_by_id(flask.g.user_id)
    learned_words = list(user.learned_user_words(count))

    # Batch load schedules to avoid N+1 queries
    user_word_ids = [uw.id for uw in learned_words]
    schedule_map = {}
    if user_word_ids:
        schedules = BasicSRSchedule.query.filter(
            BasicSRSchedule.user_word_id.in_(user_word_ids)
        ).all()
        schedule_map = {s.user_word_id: s for s in schedules}

    # Skip tokenization for list view - saves ~150ms per word (Stanza ML processing)
    json_words = [
        word.as_dictionary(
            schedule=schedule_map.get(word.id),
            with_context_tokenized=False
        )
        for word in learned_words
    ]
    return json_result(json_words)


@api.route("/total_learned_user_words", methods=["GET"])
@cross_domain
@requires_session
def total_learned_user_words():
    """
    Returns the count of unique user words that the user has learned.
    """
    user = User.find_by_id(flask.g.user_id)
    total_words_learned = user.total_learned_user_words()
    return json_result(total_words_learned)


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
    "/words_to_study_for_article/<int:article_id>",
    methods=["POST", "GET"],
)
@cross_domain
@requires_session
def words_to_study_for_article(article_id):
    user = User.find_by_id(flask.g.user_id)
    with_tokens = parse_json_boolean(request.form.get("with_tokens", "false"))

    # This approach works with UserWords (which have the scheduling logic)
    # instead of Bookmarks (which were the old approach)
    words_data = user.user_words_for_article(
        article_id,
        good_for_study=True,
        json=True,
    )

    return json_result(words_data)


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
        other_bookmarks_for_same_user_word = (
            Bookmark.query.filter(Bookmark.user_word_id == user_word.id)
            .filter(Bookmark.id != bookmark.id)
            .all()
        )

        # Clear the preferred bookmark reference if it's pointing to the bookmark we're deleting
        if user_word.preferred_bookmark_id == bookmark.id:
            user_word.preferred_bookmark = None
            db_session.add(user_word)
            db_session.flush()  # Ensure the foreign key is cleared before deletion

            # If there are other bookmarks, try to find a new preferred one
            if other_bookmarks_for_same_user_word:
                # Filter for quality bookmarks (fit_for_study)
                from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study

                quality_bookmarks = [
                    b
                    for b in other_bookmarks_for_same_user_word
                    if fit_for_study(b.user_word)
                ]

                if quality_bookmarks:
                    # Set the most recent quality bookmark as preferred
                    new_preferred = max(quality_bookmarks, key=lambda b: b.time)
                    user_word.preferred_bookmark = new_preferred
                    db_session.add(user_word)
                else:
                    # preserve UserWord but mark it as not fit for study
                    # in the future we can generate an example for this user word with the help of the robots!
                    user_word.set_unfit_for_study(db_session)
            else:
                # No other bookmarks exist - ALWAYS keep the user_word for historical data
                user_word.set_unfit_for_study(db_session)

        # Delete any ExampleSentenceContext records that reference this bookmark
        ExampleSentenceContext.query.filter(
            ExampleSentenceContext.bookmark_id == bookmark.id
        ).delete()

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
    from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
        FourLevelsPerWord,
    )

    bookmark = Bookmark.find(bookmark_id)
    user_word = bookmark.user_word

    # Fix: set preference on UserWord, not Bookmark
    user_word.user_preference = UserWordExPreference.USE_IN_EXERCISES
    user_word.update_fit_for_study(db_session)

    # Ensure a schedule exists for this UserWord
    if user_word.fit_for_study:
        FourLevelsPerWord.find_or_create(db_session, user_word)
        print(f"[USE_IN_EXERCISES] Created/found schedule for UserWord {user_word.id}")

    db_session.commit()
    return "OK"


@api.route("/dont_use_in_exercises/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def set_user_word_exercise_dislike(bookmark_id):
    from datetime import datetime

    bookmark = Bookmark.find(bookmark_id)
    user_word = bookmark.user_word
    user_word.user_preference = UserWordExPreference.DONT_USE_IN_EXERCISES
    user_word.update_fit_for_study(db_session)

    # Check if reason is "learned_already" - if so, mark as learned
    reason = request.form.get("reason", "")
    if reason == "learned_already":
        user_word.learned_time = datetime.now()

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
    bookmark.user_word.update_fit_for_study(db_session)
    db_session.commit()
    return "OK"


@api.route("/unstar_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def unstar_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = False
    bookmark.user_word.update_fit_for_study(db_session)
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


@api.route("/past_contexts/<int:user_word_id>", methods=["GET"])
@cross_domain
@requires_session
def get_past_contexts(user_word_id):
    """
    Returns only past encounter contexts (articles, videos, etc.) - excludes AI-generated examples.

    Endpoint: GET /past_contexts/<user_word_id>

    Success Response (200):
    {
        "user_word_id": 123,
        "preferred_bookmark_id": 456,
        "total_past_contexts": 2,
        "past_contexts": [
            {
                "bookmark_id": 456,
                "is_preferred": true,
                "context_type": "ARTICLE_FRAGMENT",
                "context": "The serendipity of finding this book was remarkable.",
                "title": "Article Title",
                "sentence_i": 0,
                "token_i": 1,
                "c_sentence_i": 0,
                "c_token_i": 1
            },
            {
                "bookmark_id": 789,
                "is_preferred": false,
                "context_type": "VIDEO_CAPTION",
                "context": "It was pure serendipity that we met.",
                "title": "Video Title",
                "sentence_i": 0,
                "token_i": 3,
                "c_sentence_i": 0,
                "c_token_i": 3
            }
        ]
    }

    Error Response (404):
    {
        "error": "UserWord not found or access denied"
    }
    """
    from zeeguu.core.model import UserWord, Bookmark
    from zeeguu.core.model.context_type import ContextType

    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return flask.jsonify({"error": "UserWord not found or access denied"}), 404

    # Get only non-AI-generated bookmarks for this user_word
    from zeeguu.core.model.bookmark_context import BookmarkContext

    bookmarks = (
        Bookmark.query.join(BookmarkContext, Bookmark.context_id == BookmarkContext.id)
        .outerjoin(ContextType, BookmarkContext.context_type_id == ContextType.id)
        .filter(Bookmark.user_word_id == user_word_id)
        .filter(
            or_(
                ContextType.id == None,  # Legacy bookmarks without context_type
                ContextType.type != ContextType.EXAMPLE_SENTENCE,
            )
        )
        .order_by(Bookmark.id.asc())
        .all()
    )

    past_contexts = []
    for bookmark in bookmarks:
        context_data = {
            "bookmark_id": bookmark.id,
            "is_preferred": bookmark.id == user_word.preferred_bookmark_id,
            "context": bookmark.get_context(),
            "context_type": (
                bookmark.context.context_type.type
                if bookmark.context.context_type
                else "LEGACY"
            ),
        }

        # Try to get title if available
        try:
            title = bookmark.get_source_title()
            if title:
                context_data["title"] = title
        except:
            pass

        # Add sentence and token positions
        context_data["sentence_i"] = bookmark.sentence_i
        context_data["token_i"] = bookmark.token_i
        context_data["c_sentence_i"] = bookmark.context.sentence_i
        context_data["c_token_i"] = bookmark.context.token_i

        past_contexts.append(context_data)

    result = {
        "user_word_id": user_word_id,
        "preferred_bookmark_id": user_word.preferred_bookmark_id,
        "total_past_contexts": len(past_contexts),
        "past_contexts": past_contexts,
    }

    return json_result(result)


@api.route("/all_contexts/<int:user_word_id>", methods=["GET"])
@cross_domain
@requires_session
def get_all_contexts(user_word_id):
    """
    Returns ALL contexts where a word has been encountered (past encounters + AI examples).

    Endpoint: GET /all_contexts/<user_word_id>

    Note: This includes both past encounters AND AI-generated examples.
    Use /past_contexts if you only want past encounters (articles, videos, etc.)

    Success Response (200):
    {
        "user_word_id": 123,
        "preferred_bookmark_id": 456,
        "total_contexts": 3,
        "contexts": [
            {
                "bookmark_id": 456,
                "is_preferred": true,
                "context_type": "ARTICLE_FRAGMENT",
                "context": "...",
                "title": "Article Title",
                "created_at": "2024-01-15T10:30:00"
            },
            {
                "bookmark_id": 789,
                "is_preferred": false,
                "context_type": "VIDEO_CAPTION",
                "context": "...",
                "title": "Video Title",
                "created_at": "2024-01-20T14:20:00"
            },
            {
                "bookmark_id": 101,
                "is_preferred": false,
                "context_type": "EXAMPLE_SENTENCE",
                "context": "...",
                "created_at": "2024-02-01T09:15:00"
            }
        ]
    }

    Error Response (404):
    {
        "error": "UserWord not found or access denied"
    }
    """
    from zeeguu.core.model import UserWord, Bookmark

    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return flask.jsonify({"error": "UserWord not found or access denied"}), 404

    # Get all bookmarks for this user_word
    bookmarks = (
        Bookmark.query.filter_by(user_word_id=user_word_id)
        .order_by(Bookmark.id.asc())
        .all()
    )

    contexts = []
    for bookmark in bookmarks:
        context_data = {
            "bookmark_id": bookmark.id,
            "is_preferred": bookmark.id == user_word.preferred_bookmark_id,
            "context": bookmark.get_context(),
            "context_type": (
                bookmark.context.context_type.type
                if bookmark.context.context_type
                else "UNKNOWN"
            ),
        }

        # Try to get title if available
        try:
            title = bookmark.get_source_title()
            if title:
                context_data["title"] = title
        except:
            pass

        # Add sentence and token positions
        context_data["sentence_i"] = bookmark.sentence_i
        context_data["token_i"] = bookmark.token_i
        context_data["c_sentence_i"] = bookmark.context.sentence_i
        context_data["c_token_i"] = bookmark.context.token_i

        contexts.append(context_data)

    result = {
        "user_word_id": user_word_id,
        "preferred_bookmark_id": user_word.preferred_bookmark_id,
        "total_contexts": len(contexts),
        "contexts": contexts,
    }

    return json_result(result)


@api.route("/set_preferred_bookmark/<int:user_word_id>", methods=["POST"])
@cross_domain
@requires_session
def set_preferred_bookmark(user_word_id):
    """
    Set any bookmark as the preferred context for a user word.

    Endpoint: POST /set_preferred_bookmark/<user_word_id>

    Request body (JSON):
    {
        "bookmark_id": 789  // ID of the bookmark to set as preferred
    }

    Success Response (200):
    {
        "user_word_id": 123,
        "old_preferred_bookmark_id": 456,
        "new_preferred_bookmark_id": 789,
        "message": "Preferred context updated successfully",
        "updated_bookmark": { ... }  // Full bookmark data
    }

    Error Response (400):
    {
        "error": "bookmark_id is required"
    }
    OR
    {
        "error": "Bookmark does not belong to this user word"
    }

    Error Response (404):
    {
        "error": "UserWord not found or access denied"
    }
    OR
    {
        "error": "Bookmark not found"
    }
    """
    from zeeguu.core.model import UserWord, Bookmark
    from flask import request

    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return flask.jsonify({"error": "UserWord not found or access denied"}), 404

    # Get bookmark ID from request
    bookmark_id = request.json.get("bookmark_id")

    if not bookmark_id:
        return flask.jsonify({"error": "bookmark_id is required"}), 400

    # Look up the bookmark
    bookmark = Bookmark.query.get(bookmark_id)

    if not bookmark:
        return flask.jsonify({"error": "Bookmark not found"}), 404

    # Verify this bookmark belongs to the user_word
    if bookmark.user_word_id != user_word_id:
        return (
            flask.jsonify({"error": "Bookmark does not belong to this user word"}),
            400,
        )

    # Store old preferred bookmark ID for response
    old_preferred_id = user_word.preferred_bookmark_id

    # Update the preferred bookmark
    user_word.preferred_bookmark = bookmark
    db_session.add(user_word)
    db_session.commit()

    # Refresh to get updated data
    db_session.refresh(user_word)

    return json_result(
        {
            "user_word_id": user_word_id,
            "old_preferred_bookmark_id": old_preferred_id,
            "new_preferred_bookmark_id": bookmark.id,
            "message": "Preferred context updated successfully",
            "updated_bookmark": bookmark.as_dictionary(
                with_context=True, with_context_tokenized=True
            ),
        }
    )


@api.route("/bookmark_with_context/<int:bookmark_id>", methods=["GET"])
@cross_domain
@requires_session
def bookmark_with_context(bookmark_id):
    """
    Returns a bookmark with its full context information and tokenized context.

    This endpoint returns:
    - id: bookmark ID
    - from: origin word
    - to: translation
    - from_lang: source language
    - context: the text context
    - context_tokenized: tokenized version of context
    - And other bookmark properties
    """
    try:
        bookmark = Bookmark.find(bookmark_id)

        # Verify that this bookmark belongs to the current user
        user = User.find_by_id(flask.g.user_id)
        if bookmark.user_word.user_id != user.id:
            return flask.jsonify({"error": "Bookmark not found or access denied"}), 404

        # Get bookmark data with context and tokenized context
        bookmark_data = bookmark.as_dictionary(
            with_context=True, with_context_tokenized=True, with_title=True
        )

        # Add language information
        bookmark_data["from_lang"] = bookmark.user_word.meaning.origin.language.code
        bookmark_data["to_lang"] = bookmark.user_word.meaning.translation.language.code

        return json_result(bookmark_data)

    except NoResultFound:
        return flask.jsonify({"error": "Bookmark not found"}), 404
    except Exception as e:
        return flask.jsonify({"error": "Internal server error"}), 500


@api.route("/add_custom_word", methods=["POST"])
@cross_domain
@requires_session
def add_custom_word():
    """
    Allows users to manually add a word/expression to their learning list.

    The word is immediately scheduled for exercises using the spaced repetition algorithm.

    Request body (JSON):
    {
        "word": "jo tidligere, jo bedre",  // The word/expression to learn
        "translation": "the sooner, the better",  // Translation
        "from_lang": "da",  // Source language code
        "to_lang": "en",  // Target language code
        "context": "Jo tidligere du starter, jo bedre blir resultatet"  // Optional context
    }

    Success Response (200):
    {
        "bookmark_id": 123,
        "user_word_id": 456,
        "scheduled": true,
        "level": 1
    }
    """
    from zeeguu.core.model import Language, Meaning, Bookmark
    from zeeguu.core.model.bookmark_context import BookmarkContext
    from zeeguu.core.model.context_type import ContextType
    from zeeguu.core.model.user_word import UserWord
    from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
        FourLevelsPerWord,
    )

    try:
        data = request.get_json()

        # Extract required fields
        word = data.get("word", "").strip()
        translation = data.get("translation", "").strip()
        from_lang_code = data.get("from_lang", "").strip()
        to_lang_code = data.get("to_lang", "").strip()
        context = data.get("context", "").strip()

        # Validate required fields
        if not word or not translation or not from_lang_code or not to_lang_code:
            return (
                flask.jsonify(
                    {
                        "error": "Missing required fields: word, translation, from_lang, to_lang"
                    }
                ),
                400,
            )

        # Get user and languages
        user = User.find_by_id(flask.g.user_id)
        from_lang = Language.find(from_lang_code)
        to_lang = Language.find(to_lang_code)

        if not from_lang or not to_lang:
            return flask.jsonify({"error": "Invalid language codes"}), 400

        # Create or find the meaning
        meaning = Meaning.find_or_create(
            db_session, word, from_lang_code, translation, to_lang_code
        )

        # Create UserWord with is_user_added flag
        user_word = UserWord.find_or_create(
            db_session, user, meaning, is_user_added=True  # Mark as user-added
        )

        # If no context provided, use the word itself as context
        if not context:
            context = word

        # Get the USER_EDITED_TEXT context type
        context_type = ContextType.find_or_create(
            db_session, ContextType.USER_EDITED_TEXT, commit=False
        )

        # Create bookmark context
        bookmark_context = BookmarkContext.find_or_create(
            db_session,
            context,
            context_type.type,
            from_lang,
            None,  # c_sentence_i
            None,  # c_token_i
            False,  # left_ellipsis
            False,  # right_ellipsis
        )

        # Create bookmark
        from zeeguu.core.model.text import Text
        from zeeguu.core.model.source import Source

        # Validate and find position data using shared utility
        from zeeguu.core.tokenization.word_position_finder import (
            validate_single_occurrence,
        )

        validation_result = validate_single_occurrence(word, context, from_lang)

        if not validation_result["valid"]:
            log(
                f"ERROR: Word validation failed for '{word}' in context '{context}': {validation_result['error_type']}"
            )

            # Return appropriate error response based on error type
            if validation_result["error_type"] == "multiple_occurrences":
                return (
                    flask.jsonify(
                        {
                            "error": "Ambiguous word placement",
                            "detail": validation_result["error_message"],
                            "context": context,
                        }
                    ),
                    400,
                )
            else:
                return (
                    flask.jsonify(
                        {
                            "error": (
                                "Word not found in context"
                                if validation_result["error_type"] == "not_found"
                                else "Processing failed"
                            ),
                            "detail": validation_result["error_message"],
                            "word": word,
                            "context": context,
                        }
                    ),
                    400,
                )

        # Extract position data from validation result
        position_data = validation_result["position_data"]
        sentence_i = position_data["sentence_i"]
        token_i = position_data["token_i"]
        c_sentence_i = position_data["c_sentence_i"]
        c_token_i = position_data["c_token_i"]
        total_tokens_found = position_data["total_tokens"]

        log(
            f"Successfully found user word '{word}' at position sent_i={sentence_i}, token_i={token_i}, total_tokens={total_tokens_found}"
        )

        # Create a simple context identifier for user-edited text
        # Since USER_EDITED_TEXT doesn't have a specific table mapping,
        # we just create the identifier to mark the context type
        context_identifier = ContextIdentifier(
            context_type=ContextType.USER_EDITED_TEXT
        )

        # Create bookmark using find_or_create with proper position data
        bookmark = Bookmark.find_or_create(
            db_session,
            user,
            word,
            from_lang_code,
            translation,
            to_lang_code,
            context,
            None,  # article_id - None for user-added words
            None,  # source_id - None for user-added words
            sentence_i=sentence_i,
            token_i=token_i,
            total_tokens=total_tokens_found,
            c_sentence_i=c_sentence_i,
            c_token_i=c_token_i,
            context_identifier=context_identifier,
        )

        # Set this bookmark as preferred for the user word
        user_word.preferred_bookmark = bookmark

        # Immediately schedule the word for learning
        schedule = FourLevelsPerWord.find_or_create(db_session, user_word)

        # Ensure the word is fit for study
        user_word.fit_for_study = True
        user_word.level = 1  # Start at level 1

        # Commit the user_word changes
        db_session.add(user_word)
        db_session.commit()

        return json_result(
            {
                "bookmark_id": bookmark.id,
                "user_word_id": user_word.id,
                "scheduled": True,
                "level": user_word.level,
                "message": "Word added successfully and scheduled for practice",
            }
        )

    except Exception as e:
        db_session.rollback()
        log(f"Error in add_custom_word: {str(e)}")
        return flask.jsonify({"error": "Failed to add word"}), 500
