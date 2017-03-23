import flask

from . import api
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from zeeguu.model import SimpleKnowledgeEstimator, Language


@api.route("/get_known_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_known_words(lang_code):
    """
    Words that have been learned with the help of the exercises
    """
    e = SimpleKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_known_words())

@api.route("/get_not_looked_up_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_not_looked_up_words(lang_code):
    e = SimpleKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_not_looked_up_words())


@api.route("/get_known_bookmarks/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_known_bookmarks(lang_code):
    """
    """
    e = SimpleKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_known_bookmarks())


@api.route("/get_probably_known_words/<lang_code>", methods=("GET",))
@cross_domain
@with_session
def get_probably_known_words(lang_code):
    e = SimpleKnowledgeEstimator(flask.g.user, lang_code)
    return json_result(e.get_probably_known_words())


