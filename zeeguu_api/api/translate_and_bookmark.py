import datetime
from urllib.parse import unquote_plus

import flask
import sys
from flask import request

import zeeguu

from . import api, db_session
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from zeeguu.model import Bookmark

from python_translators.query_processors.remove_unnecessary_sentences import RemoveUnnecessarySentences
from python_translators.translation_query import TranslationQuery

# When testing, we're injecting the ReverseTranslator instead of the BestEffort which
# requires API keys for the third-party services.
if not hasattr(zeeguu, "_called_from_test"):
    from python_translators.translators.best_effort_translator import DummyBestEffortTranslator as Translator
else:
    from python_translators.translators.best_effort_translator import BestEffortTranslator as Translator


@api.route("/get_possible_translations/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def get_possible_translations(from_lang_code, to_lang_code):
    """

        Returns a list of possible translations in :param to_lang_code
        for :param word in :param from_lang_code.

        You must also specify the :param context, :param url, and :param title
         of the page where the word was found.

        The context is the sentence.

        :return: json array with translations

    """

    context_str = request.form.get('context', '')
    url = request.form.get('url', '')
    #
    url = url.split('articleURL=')[-1]

    zeeguu.log(f"url before being saved: {url}")
    word_str = request.form['word']
    title_str = request.form.get('title', '')

    minimal_context, query = minimize_context(context_str, from_lang_code, word_str)

    to_lang_code = flask.g.user.native_language.code
    zeeguu.log(f'translating to... {to_lang_code}')

    translator = Translator(from_lang_code, to_lang_code)
    zeeguu.log(f"Query to translate is: {query}")
    translations = translator.translate(query).translations

    # translators talk about quality, but our users expect likelihood.
    # rename the key in the dictionary
    for t in translations:
        t['likelihood'] = t.pop("quality")
        t['source'] = t.pop('service_name')

    best_guess = translations[0]["translation"]

    Bookmark.find_or_create(db_session, flask.g.user,
                            word_str, from_lang_code,
                            best_guess, to_lang_code,
                            minimal_context, url, title_str)

    return json_result(dict(translations=translations))


@api.route("/contribute_translation/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def contribute_translation(from_lang_code, to_lang_code):
    """
    
        User contributes a translation they think is appropriate for 
         a given :param word in :param from_lang_code in a given :param context

        The :param translation is in :param to_lang_code

        Together with the two words and the textual context, you must submit
         also the :param url, :param title of the page where the original
         word and context occurred.
    
    :return: in case of success, the bookmark_id and main translation

    """

    # All these POST params are mandatory
    word_str = unquote_plus(request.form['word'])
    translation_str = request.form['translation']
    url_str = request.form.get('url', '')
    context_str = request.form.get('context', '')
    title_str = request.form.get('title', '')

    # Optional POST param
    selected_from_predefined_choices = request.form.get('selected_from_predefined_choices', '')

    minimal_context, _ = minimize_context(context_str, from_lang_code, word_str)

    bookmark = Bookmark.find_or_create(db_session, flask.g.user,
                                       word_str, from_lang_code,
                                       translation_str, to_lang_code,
                                       minimal_context, url_str, title_str)

    return json_result(dict(bookmark_id=bookmark.id))


@api.route("/delete_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def delete_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    db_session.delete(bookmark)
    db_session.commit()
    return "OK"


@api.route("/report_learned_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def report_learned_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.learned = True
    bookmark.learned_time = datetime.datetime.now()
    db_session.commit()
    return "OK"


@api.route("/star_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def star_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = True
    db_session.commit()
    return "OK"


@api.route("/unstar_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def unstar_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    bookmark.starred = False
    db_session.commit()
    return "OK"


def minimize_context(context_str, from_lang_code, word_str):
    _query = TranslationQuery.for_word_occurrence(word_str, context_str, 1, 3)
    processor = RemoveUnnecessarySentences(from_lang_code)
    query = processor.process_query(_query)
    minimal_context = query.before_context + ' ' + query.query + query.after_context
    return minimal_context, query


# --- DANGER ZONE: Deprecated Endpoint --- #
# ---------------------------------------- #

@api.route("/translate_and_bookmark/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def translate_and_bookmark(from_lang_code, to_lang_code):
    """

        @deprecated
        This should be deprecated and /get_possible_translations used instead
        However, it is still used by the zeeguu chrome extension.

        This expects in the post parameter the following:
        - word (to translate)
        - context (surrounding paragraph of the original word )
        - url (of the origin)
        - title (of the origin page)

        /get_possible_translations has very similar behavior, only that
          if focuses on returning the possible alternative translations

    :param from_lang_code:
    :param to_lang_code:
    :return:
    """

    word_str = unquote_plus(request.form['word'])

    url_str = request.form.get('url', '')
    title_str = request.form.get('title', '')
    context_str = request.form.get('context', '')

    try:
        minimal_context, query = minimize_context(context_str, from_lang_code, word_str)
        translator = Translator(from_lang_code, to_lang_code)
        translations = translator.translate(query).translations

        best_guess = translations[0]["translation"]

        bookmark = Bookmark.find_or_create(db_session, flask.g.user,
                                           word_str, from_lang_code,
                                           best_guess, to_lang_code,
                                           minimal_context, url_str, title_str)
    except ValueError as e:
        zeeguu.log(f"minimize context failed {e}on: {context_str} x {from_lang_code} x {word_str} ")
        return context_str, query

    return json_result(dict(
        bookmark_id=bookmark.id,
        translation=best_guess))
