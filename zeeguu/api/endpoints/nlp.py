from . import api

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.api.utils.json_result import json_result
from flask import request

from zeeguu.core.model.language import Language
from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL


# The spaCy endpoints served Tiago's OrderWords exercise, which no exercise
# sequence has used in a long time. Loading their three spaCy models (plus
# torch) at import cost every API worker ~1 GB. They are kept as routes so a
# caller fails loudly (500, reaches Sentry) instead of with a silent 404. If
# this is ever needed again, it belongs in its own service, like Stanza.
class SpacyEndpointsRemoved(Exception):
    pass


def _spacy_endpoint_removed():
    raise SpacyEndpointsRemoved(
        f"{request.path} was removed along with the in-process spaCy pipeline "
        "(see zeeguu/core/nlp_pipeline in git history)"
    )


for _path in (
    "/do_some_spacy",
    "/create_confusion_words",
    "/annotate_clues",
    "/get_shorter_similar_sents_in_article",
    "/get_smaller_context",
):
    api.add_url_rule(
        _path,
        endpoint=_path.strip("/"),
        view_func=cross_domain(requires_session(_spacy_endpoint_removed)),
        methods=("POST",),
    )


# ---------------------------------------------------------------------------
@api.route("/tokenize_text", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_tokenize_text():
    """
    Used by the front-end to tokenize texts. Receives a string of text, and a
    language of the text and returns the tokenized version, cosisting of a
    list of Paragraphs composed of tokens.
    """
    text = request.form.get("text", "")
    lang_code = request.form.get("language", "")
    language = Language.find(lang_code)
    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
    result = tokenizer.tokenize_text(text, language)
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/tokenize_sents", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_tokenize_sents():
    """
    Used by the front-end to tokenize sentences in texts. Receives a string of text, and
    a language of the text and returns a list with sentences (as strings).
    """
    text = request.form.get("text", "")
    lang_code = request.form.get("language", "")
    language = Language.find(lang_code)
    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
    result = tokenizer.get_sentences(text)
    return json_result(result)


# ---------------------------------------------------------------------------
@api.route("/get_paragraphs", methods=("POST",))
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def get_paragraphs():
    """
    Returns the pagraphs of a text.
    """
    text = request.form.get("text", "")
    result = get_tokenizer.split_into_paragraphs(text)
    return json_result(result)
