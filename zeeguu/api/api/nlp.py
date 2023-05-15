from . import api, db_session

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from flask import request

from zeeguu.core.nlp_pipeline import SpacyWrappers, NoiseWordsGenerator
from zeeguu.core.nlp_pipeline import AutoGECTagging

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


# ---------------------------------------------------------------------------
@api.route("/create_confusion_words", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def create_confusion_words():
    original_sent = request.form.get("original_sent", "")
    language = request.form.get("language")

    if language not in SpacyWrappers.keys():
        return "Language not supported"
    
    # We should pass the student bookmark words as a fallback when no words are found.
    noise_words = NoiseWordsGenerator[language].generate_confusion_words(original_sent)["confusion_words"]
    return json_result(noise_words)

# ---------------------------------------------------------------------------
@api.route("/annotate_clues", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def annotate_clues():
    word_with_props = request.form.get("word_with_props", "")
    original_sentence = request.form.get("original_sentence", "")
    language = request.form.get("language")

    if language not in SpacyWrappers.keys():
        return "Language not supported"
    
    updated_words = AutoGECTagging(SpacyWrappers[language], language).anottate_clues(word_with_props, original_sentence)

    return json_result(updated_words)

