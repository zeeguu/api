from urllib.parse import unquote_plus

import flask
from flask import request

import zeeguu
from translators.composite.best_effort import BestEffortTranslator

from . import api
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from zeeguu.model import Bookmark, UserWord


@api.route("/translate_and_bookmark/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def translate_and_bookmark(from_lang_code, to_lang_code):
    """
    
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
    before_context, after_context = context_str.split(word_str, 1)

    translator = BestEffortTranslator(from_lang_code, to_lang_code)

    translations = translator.ca_translate(word_str, before_context, after_context, 3)
    best_guess = translations[0]["translation"]

    bookmark = Bookmark.find_or_create(zeeguu.db.session, flask.g.user,
                                       word_str, from_lang_code,
                                       best_guess, to_lang_code,
                                       context_str, url_str, title_str)
    zeeguu.db.session.add(bookmark)
    zeeguu.db.session.commit()


    return json_result(dict(
                            bookmark_id = bookmark.id,
                            translation = best_guess))


@api.route("/get_possible_translations/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def get_possible_translations(from_lang_code, to_lang_code):
    """
    Returns a list of possible translations for this
    :param word: word to be translated
    :param from_lang_code:
    :param to_lang_code:
    :return: json array with dictionaries. each of the dictionaries contains at least
        one 'translation' and one 'translation_id' key.

        In the future we envision that the dict will contain
        other types of information, such as relative frequency,
    """

    context = request.form.get('context', '')
    url = request.form.get('url', '')
    word = request.form['word']
    title_str = request.form.get('title', '')
    before_context, after_context = context.split(word, 1)

    translator = BestEffortTranslator(from_lang_code, to_lang_code)

    translations = translator.ca_translate(word, before_context, after_context, 3)
    best_guess = translations[0]["translation"]

    bookmark = Bookmark.find_or_create(zeeguu.db.session, flask.g.user,
                                       word, from_lang_code,
                                       best_guess, to_lang_code,
                                       context, url, title_str)
    zeeguu.db.session.add(bookmark)
    zeeguu.db.session.commit()

    return json_result(dict(translations=translations))

@api.route("/contribute_translation/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def contribute_translation(from_lang_code, to_lang_code):
    """
    
        User contributes a translation they think is appropriate for 
         a given context
    
        This expects in the post parameter the following:
            - word (to translate)
            - context (surrounding paragraph of the original word )
            - url (of the origin)
            - title (of the origin page)
            - translation 
        
    :param from_lang_code:
    :param to_lang_code:
    :return: 
    """

    # All these POST params are mandatory
    word_str = unquote_plus(request.form['word'])
    translation_str = request.form['translation']
    url_str = request.form.get('url', '')
    context_str = request.form.get('context', '')
    title_str = request.form.get('title', '')

    bookmark = Bookmark.find_or_create(zeeguu.db.session, flask.g.user,
                                       word_str, from_lang_code,
                                       translation_str, to_lang_code,
                                       context_str, url_str, title_str)
    zeeguu.db.session.add(bookmark)
    zeeguu.db.session.commit()

    return json_result(dict(
                            bookmark_id = bookmark.id,
                            translation = translation_str))



@api.route("/bookmark_with_context/<from_lang_code>/<term>/<to_lang_code>/<translation>",
           methods=["POST"])
@cross_domain
@with_session
def bookmark_with_context(from_lang_code, term, to_lang_code, translation):
    """
    
        The preferred way of a user saving a word/translation/context to his  profile.
    
    :param from_lang_code:
    :param term:
    :param to_lang_code:
    :param translation:
    :return: Response containing the bookmark id
    """

    word_str = unquote_plus(term)
    translation_str = unquote_plus(translation)
    url_str = request.form.get('url', '')
    title_str = request.form.get('title', '')
    context_str = request.form.get('context', '')

    bookmark = Bookmark.find_or_create(zeeguu.db.session, flask.g.user,
                                       word_str, from_lang_code,
                                       translation_str, to_lang_code,
                                       context_str, url_str, title_str)
    zeeguu.db.session.add(bookmark)
    zeeguu.db.session.commit()

    return str(bookmark.id)


@api.route("/delete_bookmark/<bookmark_id>", methods=["POST"])
@cross_domain
@with_session
def delete_bookmark(bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    zeeguu.db.session.delete(bookmark)
    zeeguu.db.session.commit()
    return "OK"


@api.route("/add_new_translation_to_bookmark/<word_translation>/<bookmark_id>",
           methods=["POST"])
@cross_domain
@with_session
def add_new_translation_to_bookmark(word_translation, bookmark_id):
    bookmark = Bookmark.find(bookmark_id)
    translations_of_bookmark = bookmark.translations_list
    for transl in translations_of_bookmark:
        if transl.word == word_translation:
            return 'FAIL'

    translation_user_word = UserWord.find(word_translation, translations_of_bookmark[0].language)
    bookmark.add_new_translation(translation_user_word)
    zeeguu.db.session.add(translation_user_word)
    zeeguu.db.session.commit()
    return "OK"


@api.route("/delete_translation_from_bookmark/<bookmark_id>/<translation_word>",
           methods=["POST"])
@cross_domain
@with_session
def delete_translation_from_bookmark(bookmark_id, translation_word):
    bookmark = Bookmark.find(bookmark_id)
    if len(bookmark.translations_list) == 1:
        return 'FAIL'
    translation_id = -1
    for b in bookmark.translations_list:
        if translation_word == b.word:
            translation_id = b.id
            break
    if translation_id == -1:
        return 'FAIL'
    translation = UserWord.query.filter_by(
            id=translation_id
    ).first()
    bookmark.remove_translation(translation)
    zeeguu.db.session.commit()
    return "OK"


@api.route("/get_translations_for_bookmark/<bookmark_id>", methods=("GET",))
@cross_domain
@with_session
def get_translations_for_bookmark(bookmark_id):
    bookmark = Bookmark.query.filter_by(id=bookmark_id).first()

    result = [
        dict(id=translation.id,
                 word=translation.word,
                 language=translation.language.name
             )
        for translation in bookmark.translations_list]

    return json_result(result)


