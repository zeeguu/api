import os
from string import punctuation
from urllib.parse import unquote_plus

import flask
from flask import request
from python_translators.translation_query import TranslationQuery

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.parse_json_boolean import parse_json_boolean
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.translation_services.translator import (
    get_next_results,
    contribute_trans,
    get_best_translation,
    get_all_translations,
)
from zeeguu.core.crowd_translations import (
    get_own_past_translation,
)
from zeeguu.core.model import Bookmark, User, Meaning, UserWord
from zeeguu.core.model.article import Article
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.text import Text
from . import api, db_session
from zeeguu.logging import log as zeeguu_log

punctuation_extended = "»«" + punctuation
IS_DEV_SKIP_TRANSLATION = int(os.environ.get("DEV_SKIP_TRANSLATION", 0)) == 1


@api.route("/get_one_translation/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@requires_session
def get_one_translation(from_lang_code, to_lang_code):
    zeeguu_log(
        f"[TRANSLATION-ENTRY-IMMEDIATE] ENTERED get_one_translation function: from={from_lang_code}, to={to_lang_code}"
    )
    """
    :return: json array with translations
    """
    from zeeguu.logging import log

    log(
        f"[TRANSLATION-ENTRY] get_one_translation CALLED: from={from_lang_code}, to={to_lang_code}, user={flask.g.user_id}"
    )

    word_str = request.json["word"].strip(punctuation_extended)
    log(f"[TRANSLATION-ENTRY] word='{word_str}'")
    w_sent_i = request.json.get("w_sent_i", None)
    w_token_i = request.json.get("w_token_i", None)
    w_total_tokens = request.json.get("w_total_tokens", None)
    context = request.json.get("context", "").strip()
    c_paragraph_i = request.json.get("c_paragraph_i", None)
    c_sent_i = request.json.get("c_sent_i", None)
    c_token_i = request.json.get("c_token_i", None)
    article_id = request.json.get("articleID", None)
    source_id = request.json.get("source_id", None)
    in_content = request.json.get("in_content", None)
    left_ellipsis = request.json.get("left_ellipsis", None)
    right_ellipsis = request.json.get("right_ellipsis", None)
    context_identifier = ContextIdentifier.from_dictionary(
        request.json.get("context_identifier", None)
    )
    # The front end send the data in the following format:
    # ('context_identifier[context_type]', 'ArticleFragment')

    # Check if this is an MWE expression
    is_mwe_expression = request.json.get("is_mwe_expression", False)
    is_separated_mwe = request.json.get("is_separated_mwe", False)
    full_sentence_context = request.json.get("full_sentence_context", None)  # Full sentence for context
    mwe_partner_token_i = request.json.get("mwe_partner_token_i", None)  # Partner token for MWE

    # if we have an own translation that is our first "best guess"
    # ML: TODO:
    # - word translated in the same text / articleID / url should still be considered
    # even if not exactly this context
    # - a teacher's translation or a senior user's should still
    # be considered here

    print("getting own past translation....")
    # This has become less relevant since Tiago implemented the highlighting of the past translations
    # In the exercises however, if one translates a word, this can still be useful ... unless we create the
    # same history highlighting in the exercises
    user = User.find_by_id(flask.g.user_id)
    bookmark = get_own_past_translation(
        user, word_str, from_lang_code, to_lang_code, context
    )
    if bookmark:
        translation = bookmark.user_word.meaning.translation.content
        likelihood = 1
        source = "Own past translation"

        return json_result(
            {
                "translation": translation,
                "bookmark_id": bookmark.id,
                "source": source,
                "likelihood": likelihood,
            }
        )

    else:
        # TODO: must remove theurl, and title - they are not used in the calling method.
        from zeeguu.logging import log
        import time

        if IS_DEV_SKIP_TRANSLATION:
            print("Dev Skipping Translation")
            t1 = {"translation": f"T-({to_lang_code})-'{word_str}'", "likelihood": None, "source": "DEV_SKIP"}
        else:
            log(f"[TRANSLATION] Word: '{word_str}', separated_mwe={is_separated_mwe}")
            start_time = time.time()
            t1 = get_best_translation(word_str, context, from_lang_code, to_lang_code, is_separated_mwe, full_sentence_context)
            elapsed = time.time() - start_time
            log(f"[TRANSLATION] Completed in {elapsed:.3f}s: '{t1.get('translation') if t1 else 'FAILED'}'")

        log(
            f"[TRANSLATION-TIMING] About to call Bookmark.find_or_create for word='{word_str}'"
        )
        bookmark_start = time.time()
        user = User.find_by_id(flask.g.user_id)

        # Get translation source from frontend, default to 'reading'
        translation_source = request.json.get("translation_source", "reading")
        browsing_session_id = request.json.get("browsing_session_id", None)
        reading_session_id = request.json.get("reading_session_id", None)

        bookmark = Bookmark.find_or_create(
            db_session,
            user,
            word_str,
            from_lang_code,
            t1["translation"],
            to_lang_code,
            context,
            article_id,
            source_id,
            c_paragraph_i=c_paragraph_i,
            c_sentence_i=c_sent_i,
            c_token_i=c_token_i,
            left_ellipsis=left_ellipsis,
            right_ellipsis=right_ellipsis,
            sentence_i=w_sent_i,
            token_i=w_token_i,
            total_tokens=w_total_tokens,
            context_identifier=context_identifier,
            translation_source=translation_source,
            browsing_session_id=browsing_session_id,
            reading_session_id=reading_session_id,
            is_mwe=is_mwe_expression,
            mwe_partner_token_i=mwe_partner_token_i,
        )

        bookmark_elapsed = time.time() - bookmark_start
        log(
            f"[TRANSLATION-TIMING] Bookmark.find_or_create completed in {bookmark_elapsed:.3f}s for word='{word_str}'"
        )

    return json_result(
        {
            "translation": t1["translation"],
            "bookmark_id": bookmark.id,
            "source": t1["source"],
            "likelihood": t1["likelihood"],
        }
    )


@api.route(
    "/get_multiple_translations/<from_lang_code>/<to_lang_code>", methods=["POST"]
)
@cross_domain
@requires_session
def get_multiple_translations(from_lang_code, to_lang_code):
    """
    Returns a list of possible translations from multiple services.

    :return: json array with translations from Azure, Microsoft, and Google
    """

    word_str = request.form["word"].strip(punctuation_extended)
    context = request.form.get("context", "").strip()
    is_separated_mwe = request.form.get("is_separated_mwe", "").lower() == "true"
    full_sentence_context = request.form.get("full_sentence_context", "")

    translations = get_all_translations(word_str, context, from_lang_code, to_lang_code, is_separated_mwe, full_sentence_context)

    return json_result(dict(translations=translations))


@api.route(
    "/get_translations_stream/<from_lang_code>/<to_lang_code>", methods=["POST"]
)
@cross_domain
@requires_session
def get_translations_stream(from_lang_code, to_lang_code):
    """
    Stream translations as they arrive using Server-Sent Events (SSE).

    Each translation is sent as a separate SSE event, allowing the frontend
    to display results progressively rather than waiting for all services.

    :return: SSE stream with translation events
    """
    import json
    from flask import Response
    from zeeguu.core.translation_services.translator import get_translations_streaming

    word_str = request.form["word"].strip(punctuation_extended)
    context = request.form.get("context", "").strip()
    is_separated_mwe = request.form.get("is_separated_mwe", "").lower() == "true"
    full_sentence_context = request.form.get("full_sentence_context", "")

    def generate():
        for translation in get_translations_streaming(
            word_str, context, from_lang_code, to_lang_code,
            is_separated_mwe, full_sentence_context
        ):
            yield f"data: {json.dumps(translation)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
        }
    )


@api.route("/update_bookmark_translation/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def update_bookmark_translation_only(bookmark_id):
    """
    Simple endpoint to update ONLY the translation of a bookmark.

    Used from the reader when user selects an alternative translation.
    Preserves all position data (sentence_i, token_i, context, etc.)

    :param bookmark_id: ID of bookmark to update
    :return: Updated bookmark as JSON
    """
    from zeeguu.api.utils.json_result import json_result

    bookmark = Bookmark.find(bookmark_id)
    if not bookmark:
        return json_result({"error": "Bookmark not found"}, status=404)

    new_translation = request.json.get("translation")
    if not new_translation:
        return json_result({"error": "Translation required"}, status=400)

    # Find or create new Meaning with the new translation
    old_meaning = bookmark.user_word.meaning
    new_meaning = Meaning.find_or_create(
        db_session,
        old_meaning.origin.content,  # Keep same origin word
        old_meaning.origin.language.code,
        new_translation,
        old_meaning.translation.language.code,
    )

    # Find or create UserWord for the new meaning
    old_user_word = bookmark.user_word
    new_user_word = UserWord.find_or_create(
        db_session, old_user_word.user, new_meaning
    )

    # If UserWord changed, transfer learning progress
    if new_user_word.id != old_user_word.id:
        from zeeguu.core.bookmark_operations.update_bookmark import (
            transfer_learning_progress,
            cleanup_old_user_word,
        )
        transfer_learning_progress(db_session, old_user_word, new_user_word, bookmark)

        # Reassign bookmark to new UserWord
        bookmark.user_word_id = new_user_word.id
        db_session.add(bookmark)
        db_session.flush()

        # Set preferred_bookmark if needed
        if not new_user_word.preferred_bookmark:
            new_user_word.preferred_bookmark_id = bookmark.id
            db_session.add(new_user_word)

        cleanup_old_user_word(db_session, old_user_word, bookmark)

    db_session.commit()

    # Return updated bookmark
    updated = bookmark.as_dictionary(with_context=True)
    print(f"[UPDATE_TRANSLATION] Updated bookmark {bookmark_id}: '{old_meaning.origin.content}' -> '{new_translation}'")
    return json_result(updated)


@api.route("/update_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def update_bookmark_full(bookmark_id):
    """
    Full bookmark update - can change word, translation, and/or context.

    Used from WordEditForm where user can edit everything.

    This endpoint handles complex logic including:
    - Switching to new UserWord if meaning changed
    - Transferring learning progress (schedule, exercises, preferences)
    - Cleaning up orphaned UserWords
    - Validating word position in context

    See docs/BOOKMARK_UPDATE_LOGIC.md for detailed documentation.

    :param bookmark_id: ID of bookmark to update
    :return: Updated bookmark as JSON, or error response
    """
    from zeeguu.core.bookmark_operations.update_bookmark import (
        parse_update_params,
        find_or_create_meaning,
        find_or_create_context,
        transfer_learning_progress,
        cleanup_old_user_word,
        validate_and_update_position,
        format_response,
    )

    print(f"[UPDATE_BOOKMARK] ========== START: bookmark_id={bookmark_id} ==========")

    # Step 1: Parse and validate input
    bookmark = Bookmark.find(bookmark_id)
    params = parse_update_params(request.json, bookmark)

    # Unpack variables for readability
    word_str = params['word_str']
    translation_str = params['translation_str']
    context_str = params['context_str']
    context_type = params['context_type']
    origin_lang_code = params['origin_lang_code']
    translation_lang_code = params['translation_lang_code']

    # Step 2: Find or create new meaning (word/translation pair)
    meaning = find_or_create_meaning(
        db_session, word_str, origin_lang_code, translation_str, translation_lang_code
    )

    # Step 3: Check if only translation changed (word unchanged)
    # If so, we skip context recreation to preserve position data
    old_user_word = bookmark.user_word
    word_unchanged = old_user_word.meaning.origin.content == word_str

    if word_unchanged:
        # Translation-only update: keep existing text and context
        print(f"[UPDATE_BOOKMARK] Word unchanged, keeping existing text/context to preserve position")
        text = bookmark.text
        context = bookmark.context
    else:
        # Word changed: need to find/create new text and context
        text, context = find_or_create_context(db_session, context_str, context_type, bookmark)

    # Step 4: Find or create UserWord for new meaning
    # Save original context/text info BEFORE reassigning (needed for change detection later)
    old_context_id = bookmark.context_id
    old_text_id = bookmark.text_id
    print(
        f"[UPDATE_BOOKMARK] Old UserWord: {old_user_word.id}, word: '{old_user_word.meaning.origin.content}'"
    )

    new_user_word = UserWord.find_or_create(
        db_session, bookmark.user_word.user, meaning
    )
    print(
        f"[UPDATE_BOOKMARK] New UserWord: {new_user_word.id}, word: '{new_user_word.meaning.origin.content}'"
    )

    # Step 5: Transfer learning progress if UserWord changed
    if new_user_word.id != old_user_word.id:
        transfer_learning_progress(db_session, old_user_word, new_user_word, bookmark)

    # Step 6: Reassign bookmark to new entities
    bookmark.user_word_id = new_user_word.id
    bookmark.text = text
    bookmark.context = context
    db_session.add(bookmark)
    # Flush bookmark reassignment BEFORE setting preferred_bookmark_id
    # This ensures the validation sees the updated user_word_id
    db_session.flush()
    print(f"[UPDATE_BOOKMARK] Reassigned bookmark to UserWord {new_user_word.id}")

    # Set preferred_bookmark_id AFTER reassignment (if UserWord changed and doesn't have one)
    if new_user_word.id != old_user_word.id and not new_user_word.preferred_bookmark:
        new_user_word.preferred_bookmark_id = bookmark.id
        db_session.add(new_user_word)
        print(f"[UPDATE_BOOKMARK] Set preferred_bookmark_id to {bookmark.id}")

    # Step 7: Clean up old UserWord
    if new_user_word.id != old_user_word.id:
        cleanup_old_user_word(db_session, old_user_word, bookmark)
    else:
        print(
            f"[UPDATE_BOOKMARK] Same UserWord (ID: {new_user_word.id}), no cleanup needed"
        )

    # Step 8: Validate word position ONLY if the WORD changed
    # We skip validation for translation-only changes because:
    # 1. The bookmark already has valid position data (sentence_i, token_i, total_tokens)
    # 2. Re-tokenization is fragile (e.g., "l-a" vs "l-" + "a" tokenization differences)
    # 3. Context string reconstruction from tokens may differ from stored context
    if not word_unchanged:
        print(f"[UPDATE_BOOKMARK] Word changed, validating position...")
        error_response = validate_and_update_position(bookmark, word_str, context_str)
        if error_response:
            return error_response  # Validation failed, return error
    else:
        print(f"[UPDATE_BOOKMARK] Word unchanged, skipping position validation (keeping existing position data)")

    # Step 9: Commit changes and return response
    db_session.add(bookmark)
    db_session.commit()

    # Refresh to get latest fit_for_study status
    db_session.refresh(new_user_word)

    return format_response(bookmark, new_user_word)


# ================================================
# NOTE: Only used from the tests at the moment.
# ================================================
# The front-end user contributing their own translation is done via /update_bookmark
@api.route("/contribute_translation/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@requires_session
def contribute_translation(from_lang_code, to_lang_code):
    """

    NOTE: This is only used by the tests

        User contributes a translation they think is appropriate for
         a given :param word in :param from_lang_code in a given :param context

        The :param translation is in :param to_lang_code

        Together with the two words and the textual context, you must submit
         also the :param url, :param title of the page where the original
         word and context occurred.

    :return: in case of success, the bookmark_id and main translation

    """

    # All these POST params are mandatory
    request_params = request.json
    word_str = unquote_plus(request_params["word"])
    translation_str = request_params["translation"]
    url = request_params.get("url", "")
    context_str = request_params.get("context", "")
    w_sent_i = request_params.get("w_sent_i", None)
    w_token_i = request_params.get("w_token_i", None)
    w_total_tokens = request_params.get("w_total_tokens", None)
    context = request_params.get("context", "").strip()
    c_paragraph_i = request_params.get("c_paragraph_i", None)
    c_sent_i = request_params.get("c_sent_i", None)
    c_token_i = request_params.get("c_token_i", None)
    source_id = request_params.get("source_id", None)
    in_content = parse_json_boolean(request_params.get("in_content", None))
    left_ellipsis = parse_json_boolean(request_params.get("left_ellipsis", None))
    right_ellipsis = parse_json_boolean(request_params.get("right_ellipsis", None))
    context_identifier = ContextIdentifier.from_dictionary(
        request_params.get("context_identifier", None)
    )
    # when a translation is added by hand, the servicename_translation is None
    # thus we set it to MANUAL
    service_name = request_params.get("servicename_translation", "MANUAL")
    article_id = None
    if "articleID" in url:
        article_id = url.split("articleID=")[-1]
        url = Article.query.filter_by(id=article_id).one().url.as_canonical_string()
    elif "articleURL" in url:
        url = url.split("articleURL=")[-1]
    elif "article?id=" in url:
        article_id = url.split("article?id=")[-1]
        url = Article.query.filter_by(id=article_id).one().url.as_canonical_string()
    else:
        # the url comes from elsewhere not from the reader, so we find or create the article
        if url != "":
            article = Article.find_or_create(db_session, url)
            article_id = article.id

    # Optional POST param
    selected_from_predefined_choices = request_params.get(
        "selected_from_predefined_choices", ""
    )
    user = User.find_by_id(flask.g.user_id)
    bookmark = Bookmark.find_or_create(
        db_session,
        user,
        word_str,
        from_lang_code,
        translation_str,
        to_lang_code,
        context,
        article_id,
        source_id=source_id,
        c_paragraph_i=c_paragraph_i,
        c_sentence_i=c_sent_i,
        c_token_i=c_token_i,
        in_content=in_content,
        left_ellipsis=left_ellipsis,
        right_ellipsis=right_ellipsis,
        sentence_i=w_sent_i,
        token_i=w_token_i,
        total_tokens=w_total_tokens,
        context_identifier=context_identifier,
    )

    # Inform apimux about translation selection
    data = {
        "word_str": word_str,
        "translation_str": translation_str,
        "url": url,
        "context_size": len(context_str),
        "service_name": service_name,
    }
    contribute_trans(data)

    return json_result(dict(bookmark_id=bookmark.id))


@api.route("/basic_translate/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@requires_session
def basic_translate(from_lang_code, to_lang_code):
    phrase = request.form["phrase"].strip(punctuation_extended)

    query = TranslationQuery.for_word_occurrence(phrase, "", 1, 7)

    payload = {
        "from_lang_code": from_lang_code,
        "to_lang_code": to_lang_code,
        "word": phrase,
        "query": query,
        "context": "",
    }

    translations = get_next_results(
        payload,
        number_of_results=1,
    ).translations

    best_guess = translations[0]["translation"]
    likelihood = translations[0].pop("quality")
    source = translations[0].pop("service_name")

    return json_result(
        {
            "translation": best_guess,
            "source": source,
            "likelihood": likelihood,
        }
    )
