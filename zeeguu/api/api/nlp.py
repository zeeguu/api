from . import api, db_session

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from flask import request

from zeeguu.core.nlp_pipeline import SpacyWrappers

# ---------------------------------------------------------------------------
@api.route("/do_some_spacy", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def do_some_spacy():

    phrase = request.form.get("phrase", "")
    language = request.form.get("language")

    if language not in SpacyWrappers.keys():
        return "Language not supported"

    tokens = SpacyWrappers[language].tokenize_sentence(phrase)

    return json_result(tokens)
