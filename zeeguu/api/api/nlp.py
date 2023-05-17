from . import api, db_session

from .utils.route_wrappers import cross_domain, with_session
from .utils.json_result import json_result
from flask import request

from zeeguu.core.nlp_pipeline import SpacyWrappers, NoiseWordsGenerator
from zeeguu.core.nlp_pipeline import AutoGECTagging

import heapq
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
    noise_words = NoiseWordsGenerator[language].generate_confusion_words(original_sent)
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

# ---------------------------------------------------------------------------
@api.route("/get_sentences_for_wo", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@with_session
def get_sentences_for_wo():
    article_text = request.form.get("article_text", "")
    bookmark_context = request.form.get("bookmark_context", "")
    language = request.form.get("language")

    if language not in SpacyWrappers.keys():
        return "Language not supported"
    
    nlp_pipe = SpacyWrappers[language]
    sentences = nlp_pipe.get_sent_list(article_text)
    filtered_sentences = [sent for sent in sentences if len(nlp_pipe.tokenize_sentence(sent)) <= 15]
    
    context_doc = nlp_pipe.spacy_pipe(bookmark_context)
    heap = []
    for f_sent in filtered_sentences:
        sent_doc = nlp_pipe.spacy_pipe(f_sent)
        heapq.heappush(heap, (-context_doc.similarity(sent_doc), f_sent))

    _, most_similar_sent = heap.pop()
    return json_result(heap)
