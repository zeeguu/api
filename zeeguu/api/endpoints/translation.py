import os
from string import punctuation
from urllib.parse import unquote_plus

import flask
from flask import request
from python_translators.translation_query import TranslationQuery

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.parse_json_boolean import parse_json_boolean
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.translator import (
    get_next_results,
    contribute_trans,
    google_contextual_translate,
    microsoft_contextual_translate,
)
from zeeguu.core.crowd_translations import (
    get_own_past_translation,
)
from zeeguu.core.model import Bookmark, User, Meaning
from zeeguu.core.model.article import Article
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.bookmark_context import ContextIdentifier
from zeeguu.core.model.text import Text
from . import api, db_session

punctuation_extended = "»«" + punctuation
IS_DEV_SKIP_TRANSLATION = int(os.environ.get("DEV_SKIP_TRANSLATION", 0)) == 1


@api.route("/get_one_translation/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@requires_session
def get_one_translation(from_lang_code, to_lang_code):
    """
    :return: json array with translations
    """
    word_str = request.json["word"].strip(punctuation_extended)
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

    query = TranslationQuery.for_word_occurrence(word_str, context, 1, 7)

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
        translation = bookmark.meaning.translation.content
        likelihood = 1
        source = "Own past translation"
        print(f"about to return {bookmark}")
        t1 = {translation: translation, likelihood: likelihood, source: source}
    else:
        # TODO: must remove theurl, and title - they are not used in the calling method.
        if IS_DEV_SKIP_TRANSLATION:
            print("Dev Skipping Translation")
            translation = f"T-({to_lang_code})-'{word_str}'"
            likelihood = None
            source = "DEV_SKIP"
            t1 = {translation: translation, likelihood: likelihood, source: source}
        else:
            data = {
                "source_language": from_lang_code,
                "target_language": to_lang_code,
                "word": word_str,
                "query": query,
                "context": context,
            }
            # The API Mux is misbehaving and will only serve the non-contextual translators after a while
            # For now hardcoding google on the first place and msft as a backup

            t1 = google_contextual_translate(data)
            if not t1:
                t1 = microsoft_contextual_translate(data)

        user = User.find_by_id(flask.g.user_id)
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
    Returns a list of possible translations in :param to_lang_code
    for :param word in :param from_lang_code except a translation
    from :service

    You must also specify the :param context, :param url, and :param title
     of the page where the word was found.

    The context is the sentence.

    :return: json array with translations
    """

    word_str = request.form["word"].strip(punctuation_extended)
    context = request.form.get("context", "").strip()
    number_of_results = int(request.form.get("numberOfResults", -1))
    translation_to_exclude = request.form.get("translationToExclude", "")
    service_to_exclude = request.form.get("serviceToExclude", "")

    exclude_services = [] if service_to_exclude == "" else [service_to_exclude]
    exclude_results = (
        [] if translation_to_exclude == "" else [translation_to_exclude.lower()]
    )

    query = TranslationQuery.for_word_occurrence(word_str, context, 1, 7)

    data = {
        "source_language": from_lang_code,
        "target_language": to_lang_code,
        "word": word_str,
        "query": query,
        "context": context,
    }
    t1 = google_contextual_translate(data)
    t2 = microsoft_contextual_translate(data)

    return json_result(dict(translations=[t1, t2]))


@api.route("/update_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@requires_session
def update_translation(bookmark_id):
    """

        User updates a bookmark

    :return: in case of success, the bookmark_id

    """

    # All these POST params are mandatory
    word_str = unquote_plus(request.json["word"]).strip(punctuation_extended)
    translation_str = request.json["translation"]
    context_str = request.json.get("context", "").strip()
    context_identifier = request.json.get("context_identifier", None)
    context_type = context_identifier["context_type"]

    bookmark = Bookmark.find(bookmark_id)

    meaning = Meaning.find_or_create(
        db_session,
        word_str,
        bookmark.meaning.origin.language.code,
        translation_str,
        bookmark.meaning.translation.language.code,
    )

    prev_context = BookmarkContext.find_by_id(bookmark.context_id)
    prev_text = Text.find_by_id(bookmark.text_id)

    is_same_text = prev_text.content == context_str
    is_same_context = prev_context and prev_context.get_content() == context_str

    text = Text.find_or_create(
        db_session,
        context_str,
        bookmark.meaning.origin.language,
        bookmark.text.url,
        bookmark.text.article if is_same_text else None,
        prev_text.paragraph_i if is_same_text else None,
        prev_text.sentence_i if is_same_text else None,
        prev_text.token_i if is_same_text else None,
        prev_text.in_content if is_same_text else None,
        prev_text.left_ellipsis if is_same_text else None,
        prev_text.right_ellipsis if is_same_text else None,
    )

    ## TO-DO: Update context type once web sends that information.
    context = BookmarkContext.find_or_create(
        db_session,
        context_str,
        context_type,
        bookmark.meaning.origin.language,
        prev_context.sentence_i if is_same_context else None,
        prev_context.token_i if is_same_context else None,
        prev_context.left_ellipsis if is_same_context else None,
        prev_context.right_ellipsis if is_same_context else None,
    )

    bookmark.meaning = meaning
    bookmark.text = text
    bookmark.context = context

    if (
        not is_same_text
        or not is_same_context
        or bookmark.meaning.origin.content != word_str
    ):
        # In the frontend it's mandatory that the bookmark is in the text,
        # so we update the pointer.
        from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

        tokenizer = get_tokenizer(bookmark.meaning.origin.language, TOKENIZER_MODEL)
        # Tokenized text returns paragraph, sents, token
        # Since we know there is not multiple paragraphs, we take the first
        tokenized_text = tokenizer.tokenize_text(context.get_content(), False)
        tokenized_bookmark = tokenizer.tokenize_text(word_str, False)
        try:
            first_token_ocurrence = next(
                filter(lambda t: t.text == tokenized_bookmark[0].text, tokenized_text)
            )
        except StopIteration as e:
            from zeeguu.logging import print_and_log_to_sentry

            print_and_log_to_sentry(e)
            return "ERROR"

        bookmark.sentence_i = first_token_ocurrence.sent_i
        bookmark.token_i = first_token_ocurrence.token_i
        bookmark.total_tokens = len(tokenized_bookmark)
        if not is_same_context:
            from zeeguu.core.model.context_type import ContextType

            bookmark.context.context_type = ContextType.find_by_type(
                ContextType.USER_EDITED_TEXT
            )

    bookmark.meaning = meaning
    db_session.add(bookmark)

    updated_bookmark = bookmark.as_dictionary(
        with_exercise_info=True, with_context_tokenized=True, with_context=True
    )
    db_session.commit()

    return json_result(updated_bookmark)


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
