from datetime import datetime
from urllib import unquote_plus

import flask
from flask import request

import zeeguu
from translators import GlosbeTranslator
from translators import GoogleTranslator

from . import api
from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from zeeguu.model import Bookmark, Language, Text, Url, UserWord




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
    :param from_lang_code:
    :param to_lang_code:
    :return:
    """

    word_str = unquote_plus(request.form['word'])

    url_str = request.form.get('url', '')
    title_str = request.form.get('title', '')
    context_str = request.form.get('context', '')

    translation_str = main_translation(word_str, context_str, from_lang_code, to_lang_code)

    id = bookmark_with_context(from_lang_code, to_lang_code, word_str, url_str, title_str, context_str, translation_str)

    return json_result(dict(
                            bookmark_id = id,
                            translation = translation_str))


def bookmark_with_context(from_lang_code, to_lang_code, word_str, url_str, title_str, context_str, translation_str):
    """
        This function will lookup a given word-text pair, and if found, it will return
     that bookmark rather than a new one

    :param from_lang_code:
    :param to_lang_code:
    :param word_str:
    :param url_str:
    :param title_str:
    :param context_str:
    :param translation_str:
    :return:
    """
    from_lang = Language.find(from_lang_code)
    to_lang = Language.find(to_lang_code)

    user_word = UserWord.find(word_str, from_lang)
    url = Url.find(url_str, title_str)
    context = Text.find_or_create(context_str, from_lang, url)
    translation = UserWord.find(translation_str, to_lang)

    try:
        bookmark = Bookmark.find_all_by_user_word_and_text(flask.g.user, user_word, context)[0]
    #     TODO: Think about updating the date of this bookmark, or maybe creating a duplicate
    #       otherwise, in the history this translation will not be visible!

    except Exception:
        bookmark = Bookmark(user_word, translation, flask.g.user, context, datetime.now())

    zeeguu.db.session.add(bookmark)
    zeeguu.db.session.add(context)
    zeeguu.db.session.add(user_word)
    zeeguu.db.session.add(url)
    zeeguu.db.session.commit()

    return str(bookmark.id)


@api.route("/bookmark_with_context/<from_lang_code>/<term>/<to_lang_code>/<translation>",
           methods=["POST"])
@cross_domain
@with_session
def bookmark_with_context_api(from_lang_code, term, to_lang_code, translation):
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

    id = bookmark_with_context(from_lang_code, to_lang_code, word_str, url_str, title_str, context_str, translation_str)

    return id


@api.route("/delete_bookmark/<bookmark_id>",
           methods=["POST"])
@cross_domain
@with_session
def delete_bookmark(bookmark_id):
    # Beware, the web app uses the /delete_bookmark endpoint from the gym API
    bookmark = Bookmark.query.filter_by(
            id=bookmark_id
    ).first()

    try:
        zeeguu.db.session.delete(bookmark)
        zeeguu.db.session.commit()
        return "OK"
    except Exception:
        return "FAIL"


@api.route("/add_new_translation_to_bookmark/<word_translation>/<bookmark_id>",
           methods=["POST"])
@cross_domain
@with_session
def add_new_translation_to_bookmark(word_translation, bookmark_id):
    bookmark = Bookmark.query.filter_by(
            id=bookmark_id
    ).first()
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
    bookmark = Bookmark.query.filter_by(
            id=bookmark_id
    ).first()
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
             # ,ranked_word=translation.rank
             # this thing seems meaningless. should be removed
             # however, for now commented out since i'm not sure.
             )
        for translation in bookmark.translations_list]

    return json_result(result)





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

    translations_json = []
    context = request.form.get('context', '')
    url = request.form.get('url', '')
    word = request.form['word']
    title_str = request.form.get('title', '')

    main = main_translation(word, context, from_lang_code, to_lang_code)
    alternatives = alternative_translations(word, context, from_lang_code, to_lang_code)

    bookmark_with_context(from_lang_code, to_lang_code, word, url, title_str, context, main)

    lan = Language.find(to_lang_code)
    likelihood = 1.0
    for translation in alternatives:
        wor = UserWord.find(translation, lan)
        zeeguu.db.session.add(wor)
        zeeguu.db.session.commit()
        t_dict = dict(translation_id= wor.id,
                 translation=translation,
                 likelihood=likelihood)
        translations_json.append(t_dict)
        likelihood -= 0.01

    return json_result(dict(translations=translations_json))


# Warning:
# Might be deprecated at some point... or at least, reduced to translating single words...
# It would make more sense to use translate_and_bookmark instead
#
# Sincerely your's,
# Tom Petty and the Zeeguus
#
# @api.route("/translate/<from_lang_code>/<to_lang_code>", methods=["POST"])
# @cross_domain
# def translate(from_lang_code, to_lang_code):
#     """
#     This will be deprecated soon...
#     # TODO: Zeeguu Translate for Android should stop relying on this
#     :param word:
#     :param from_lang_code:
#     :param to_lang_code:
#     :return:
#     """
#
#     # print str(request.get_data())
#     # context = request.form.get('context', '')
#     # url = request.form.get('url', '')
#     word = request.form['word']
#     main_translation, alternatives = translation_service.translate_from_to(word, from_lang_code, to_lang_code)
#
#     return main_translation


def main_translation(word_str, context_str, from_lang_code, to_lang_code):
    # Assume we're translating the first occurrence of the given word in the context
    left_context, right_context = context_str.split(word_str, 1)

    try:
        t = GoogleTranslator()
        translation = t.ca_translate(word_str, from_lang_code, to_lang_code, left_context, right_context)
    except Exception as e:
        print e

        # In case Google fails, we fallback on Glosbe
        t = GlosbeTranslator()
        translation = t.translate(word_str,from_lang_code, to_lang_code)

    return translation


def alternative_translations(word_str, context_str, from_lang_code, to_lang_code):
    try:
        t = GlosbeTranslator()
        translations = t.translate(word_str, from_lang_code, to_lang_code, 10)
        if not translations:
            raise Exception("nothing found in Glosbe. Trying out GoogleTranslator")
        return translations
    except Exception as e:
        print e
        t = GoogleTranslator()
        translation = t.translate(word_str, from_lang_code, to_lang_code)
        return [translation]


def translate(word_str, context_str, from_lang_code, to_lang_code):

    translation = main_translation(word_str, context_str, from_lang_code, to_lang_code)
    return translation, []
