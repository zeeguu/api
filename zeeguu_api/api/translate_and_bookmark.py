import datetime
from urllib.parse import unquote_plus

import flask
from flask import request

import zeeguu_core

from . import api, db_session
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from zeeguu_core.model import Bookmark, Article
from zeeguu_api.api.translator import (
    minimize_context, get_all_translations, contribute_trans)


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
    data = {"from_lang_code": from_lang_code, "to_lang_code": to_lang_code}
    data["context"] = request.form.get('context', '')
    url = request.form.get('url', '')
    data["url"] = url
    article_id = None
    if 'articleID' in url:
        article_id = url.split('articleID=')[-1]
        url = Article.query.filter_by(id=article_id).one().url.as_canonical_string()
    elif 'articleURL' in url:
        url = url.split('articleURL=')[-1]
    else:
        # the url comes from elsewhere not from the reader, so we find or creat the article
        article = Article.find_or_create(db_session, url)
        article_id = article.id
    zeeguu_core.log(f"url before being saved: {url}")
    word_str = request.form['word']
    data["word"] = word_str
    title_str = request.form.get('title', '')
    data["title"] = title_str

    zeeguu_core.log(f'translating to... {data["to_lang_code"]}')
    minimal_context, query = minimize_context(
        data["context"], data["from_lang_code"], data["word"])
    zeeguu_core.log(f"Query to translate is: {query}")
    data["query"] = query
    translations = get_all_translations(data).translations
    zeeguu_core.log(f"Got translations: {translations}")

    # translators talk about quality, but our users expect likelihood.
    # rename the key in the dictionary
    for t in translations:
        t['likelihood'] = t.pop("quality")
        t['source'] = t.pop('service_name')

    best_guess = translations[0]["translation"]

    Bookmark.find_or_create(db_session, flask.g.user,
                            word_str, from_lang_code,
                            best_guess, to_lang_code,
                            minimal_context, url, title_str, article_id)

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
    url = request.form.get('url', '')
    context_str = request.form.get('context', '')
    title_str = request.form.get('title', '')
    service_name = request.form.get('servicename_translation', 'MANUAL')

    article_id = None
    if 'articleID' in url:
        article_id = url.split('articleID=')[-1]
        url = Article.query.filter_by(id=article_id).one().url.as_canonical_string()
    elif 'articleURL' in url:
        url = url.split('articleURL=')[-1]
    else:
        # the url comes from elsewhere not from the reader, so we find or creat the article
        article = Article.find_or_create(db_session, url)
        article_id = article.id

    # Optional POST param
    selected_from_predefined_choices = request.form.get('selected_from_predefined_choices', '')

    minimal_context, _ = minimize_context(context_str, from_lang_code, word_str)

    bookmark = Bookmark.find_or_create(db_session, flask.g.user,
                                       word_str, from_lang_code,
                                       translation_str, to_lang_code,
                                       minimal_context, url, title_str, article_id)
    # Inform apimux about translation selection
    data = {"word_str": word_str, "translation_str": translation_str,
            "url": url, "context_size": len(context_str),
            "service_name": service_name}
    contribute_trans(data)
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

    data = {"from_lang_code": from_lang_code, "to_lang_code": to_lang_code}
    word_str = unquote_plus(request.form['word'])
    data["word"] = word_str
    url_str = request.form.get('url', '')
    data["url"] = url_str

    title_str = request.form.get('title', '')
    data["title"] = title_str
    context_str = request.form.get('context', '')
    data["context"] = context_str

    # the url comes from elsewhere not from the reader, so we find or creat the article
    article = Article.find_or_create(db_session, url_str)
    article_id = article.id

    try:

        minimal_context, query = minimize_context(
            data["context"], data["from_lang_code"], data["word"])
        data["query"] = query
        translations = get_all_translations(data).translations

        best_guess = translations[0]["translation"]

        bookmark = Bookmark.find_or_create(db_session, flask.g.user,
                                           word_str, from_lang_code,
                                           best_guess, to_lang_code,
                                           minimal_context, url_str, title_str, article_id)
    except ValueError as e:
        zeeguu_core.log(f"minimize context failed {e}on: {context_str} x {from_lang_code} x {word_str} ")
        return context_str, query

    return json_result(dict(
        bookmark_id=bookmark.id,
        translation=best_guess))
