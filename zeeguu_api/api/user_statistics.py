import flask

from . import api
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from zeeguu.model import SethiKnowledgeEstimator, Language


@api.route("/get_not_encountered_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_not_encountered_words(lang_code):
    return json_result(flask.g.user.get_not_encountered_words(Language.find(lang_code)))


# MAKES NO SENSE TO HAVE BOTH Known Bookmarks and LEarned Bookmarks
# Must refactor these
@api.route("/get_known_bookmarks/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_known_bookmarks(lang_code):
    e = SethiKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_known_bookmarks())

@api.route("/get_learned_bookmarks/<lang>", methods=("GET",))
@cross_domain
@with_session
def get_learned_bookmarks(lang):
    lang = Language.find(lang)

    estimator = SethiKnowledgeEstimator(flask.g.user, lang.id)
    bk_list = [
        dict(
            id=bookmark.id,
            origin=bookmark.origin.word,
            text=bookmark.text.content)
        for bookmark in estimator.learned_bookmarks()]

    return json_result(bk_list)



@api.route("/get_known_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_known_words(lang_code):
    """
    :param lang_code: only show the words for a given language (e.g. 'de')
    :return: Returns all the bookmarks of a given user in the given lang
    """
    e = SethiKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.known_words_list())


@api.route("/get_probably_known_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_probably_known_words(lang_code):
    e = SethiKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_probably_known_words())


@api.route("/get_lower_bound_percentage_of_basic_vocabulary", methods=["GET"])
@cross_domain
@with_session
def get_lower_bound_percentage_of_basic_vocabulary():
    """
    :return: string representation of positive sub-unitary float
    """
    e = SethiKnowledgeEstimator(flask.g.user)
    return str(e.get_lower_bound_percentage_of_basic_vocabulary())


@api.route("/get_upper_bound_percentage_of_basic_vocabulary", methods=("GET",))
@cross_domain
@with_session
def get_upper_bound_percentage_of_basic_vocabulary():
    """

    :return: string representation of positive, sub-unitary float
    """
    e = SethiKnowledgeEstimator(flask.g.user)
    return str(e.get_upper_bound_percentage_of_basic_vocabulary())


@api.route("/get_lower_bound_percentage_of_extended_vocabulary", methods=("GET",))
@cross_domain
@with_session
def get_lower_bound_percentage_of_extended_vocabulary():
    """

    :return: string representation of positive sub-unitary float
    """
    e = SethiKnowledgeEstimator(flask.g.user)
    return str(e.get_lower_bound_percentage_of_extended_vocabulary())


@api.route("/get_upper_bound_percentage_of_extended_vocabulary", methods=("GET",))
@cross_domain
@with_session
def get_upper_bound_percentage_of_extended_vocabulary():
    """

    :return: string representation of positive sub-unitary float
    """
    e = SethiKnowledgeEstimator(flask.g.user)
    return str(e.get_upper_bound_percentage_of_extended_vocabulary())


# returns the percentage of how many bookmarks are known to the user out of all the bookmarks
@api.route("/get_percentage_of_probably_known_bookmarked_words", methods=("GET",))
@cross_domain
@with_session
def get_percentage_of_probably_known_bookmarked_words():
    """

    :return: string representation of positive sub-unitary float
    """
    e = SethiKnowledgeEstimator(flask.g.user)
    return str(e.get_percentage_of_probably_known_bookmarked_words())




@api.route("/get_not_looked_up_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_not_looked_up_words(lang_code):
    e = SethiKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_not_looked_up_words())
