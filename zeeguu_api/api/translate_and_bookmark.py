from urllib.parse import unquote_plus

import flask
from flask import request
from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from zeeguu_api.api.translator import (
    minimize_context,
    get_next_results,
    contribute_trans,
)
from zeeguu_core.crowd_translations import (
    own_or_crowdsourced_translation,
    own_translation,
)
from zeeguu_core.model import (
    Bookmark,
    Article,
    ExerciseSource,
    ExerciseOutcome,
)
from . import api, db_session
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session


@api.route("/get_next_translations/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def get_next_translations(from_lang_code, to_lang_code):
    """
    Returns a list of possible translations in :param to_lang_code
    for :param word in :param from_lang_code.

    You must also specify the :param context, :param url, and :param title
     of the page where the word was found.

    The context is the sentence.

    :return: json array with translations
    """

    data = {"from_lang_code": from_lang_code, "to_lang_code": to_lang_code}
    data["context"] = request.form.get("context", "")
    url = request.form.get("url", "")
    number_of_results = int(request.form.get("numberOfResults", -1))

    service_name = request.form.get("service", "")

    exclude_services = [] if service_name == "" else [service_name]
    currentTranslation = request.form.get("currentTranslation", "")

    exclude_results = [] if currentTranslation == "" else [currentTranslation.lower()]
    data["url"] = url
    article_id = request.form.get("articleId", None)

    if article_id == None:
        if "articleID" in url:
            article_id = url.split("articleID=")[-1]
            url = Article.query.filter_by(id=article_id).one().url.as_canonical_string()
        elif "articleURL" in url:
            url = url.split("articleURL=")[-1]
        else:
            # the url comes from elsewhere not from the reader, so we find or creat the article
            article = Article.find_or_create(db_session, url)
            article_id = article.id
    zeeguu_core.log(f"url before being saved: {url}")
    word_str = request.form["word"]
    data["word"] = word_str
    title_str = request.form.get("title", "")
    data["title"] = title_str

    zeeguu_core.log(f'translating to... {data["to_lang_code"]}')
    minimal_context, query = minimize_context(
        data["context"], data["from_lang_code"], data["word"]
    )
    zeeguu_core.log(f"Query to translate is: {query}")
    data["query"] = query

    first_call_for_this_word = len(exclude_services) == 0

    if first_call_for_this_word:
        translations = own_or_crowdsourced_translation(
            flask.g.user, word_str, from_lang_code, to_lang_code, minimal_context
        )
        if translations:
            return json_result(dict(translations=translations))

    translations = get_next_results(
        data,
        exclude_services=exclude_services,
        exclude_results=exclude_results,
        number_of_results=number_of_results,
    ).translations

    # translators talk about quality, but our users expect likelihood.
    # rename the key in the dictionary
    for t in translations:
        t["likelihood"] = t.pop("quality")
        t["source"] = t["service_name"]

    if len(translations) > 0 and first_call_for_this_word:
        best_guess = translations[0]["translation"]

        Bookmark.find_or_create(
            db_session,
            flask.g.user,
            word_str,
            from_lang_code,
            best_guess,
            to_lang_code,
            minimal_context,
            url,
            title_str,
            article_id,
        )

    return json_result(dict(translations=translations))


@api.route("/get_one_translation/<from_lang_code>/<to_lang_code>", methods=["POST"])
@cross_domain
@with_session
def get_one_translation(from_lang_code, to_lang_code):
    """

    Addressing some of the problems with the
    get_next_translations...
    - it should be separated in get_first and get_alternatives
    - alternatively it can be get one and get all

    To think about:
    - it would also make sense to separate translation from
    logging; or at least, allow for situations where a translation
    is not associated with an url... or?

    :return: json array with translations
    """

    word_str = request.form["word"]
    url = request.form.get("url")
    title_str = request.form.get("title", "")
    context = request.form.get("context", "")
    article_id = request.form.get("articleID", None)

    minimal_context, query = minimize_context(context, from_lang_code, word_str)

    best_guess = own_translation(
        flask.g.user, word_str, from_lang_code, to_lang_code, minimal_context
    )

    if best_guess:
        source = "Own past translation"
        likelihood = 1

    else:
        # we don't have an own / teacher translation; we try to translate; get the first result

        translations = get_next_results(
            {
                "from_lang_code": from_lang_code,
                "to_lang_code": to_lang_code,
                "url": request.form.get("url"),
                "word": word_str,
                "title": title_str,
                "query": query,
                "context": minimal_context,
            },
            number_of_results=1,
        ).translations

        if len(translations) == 1:
            best_guess = translations[0]["translation"]
            likelihood = translations[0].pop("quality")
            source = translations[0].pop("service_name")

    if not article_id and "article?id=" in url:
        article_id = url.split("article?id=")[-1]

    if article_id:
        article_id = int(article_id)
    else:
        # the url comes from elsewhere not from the reader, so we find or create the article
        article = Article.find_or_create(db_session, url)
        article_id = article.id

    bookmark = Bookmark.find_or_create(
        db_session,
        flask.g.user,
        word_str,
        from_lang_code,
        best_guess,
        to_lang_code,
        minimal_context,
        url,
        title_str,
        article_id,
    )

    return json_result(
        {
            "translation": best_guess,
            "bookmark_id": bookmark.id,
            "source": source,
            "likelihood": likelihood,
        }
    )


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
    word_str = unquote_plus(request.form["word"])
    translation_str = request.form["translation"]
    url = request.form.get("url", "")
    context_str = request.form.get("context", "")
    title_str = request.form.get("title", "")
    # when a translation is added by hand, the servicename_translation is None
    # thus we set it to MANUAL
    service_name = request.form.get("servicename_translation", "MANUAL")

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
        article = Article.find_or_create(db_session, url)
        article_id = article.id

    # Optional POST param
    selected_from_predefined_choices = request.form.get(
        "selected_from_predefined_choices", ""
    )

    minimal_context, _ = minimize_context(context_str, from_lang_code, word_str)

    bookmark = Bookmark.find_or_create(
        db_session,
        flask.g.user,
        word_str,
        from_lang_code,
        translation_str,
        to_lang_code,
        minimal_context,
        url,
        title_str,
        article_id,
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
