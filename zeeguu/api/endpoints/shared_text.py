"""
Text shared into Zeeguu from another app, typically a chat message (WhatsApp,
Signal, SMS) sent through the phone's share sheet.

A message is a few lines of someone else's conversation, not an article: it
is not stored, recommended or listed anywhere. The reader only needs it
tokenized so words can be tapped. Those taps go through /translate_word like
any other, so the words still become the learner's bookmarks, with the
message sentence as their context (context type SharedText).
"""

import flask
from flask import request
from langdetect import detect_langs
from langdetect.lang_detect_exception import LangDetectException

from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import User
from zeeguu.core.model.language import Language

from . import api

# A chat message, or a few forwarded together. Longer than this is an article
# pasted into a chat, and the reader for those is the article flow.
MAX_SHARED_TEXT_CHARS = 5000

# Below this, langdetect's guess is too often wrong to override the language
# the learner is learning: "Ok", "Tak!", a name and an emoji.
_MIN_CONFIDENCE_TO_OVERRIDE = 0.9

# If the learned language is among langdetect's candidates at all, keep it.
# Close languages split the vote: a Danish message often comes back as mostly
# Norwegian with some Danish, and the Danish learner meant Danish.
_LEARNED_LANGUAGE_CANDIDATE_FLOOR = 0.1


def _shared_text_or_error():
    text = (request.form.get("text") or "").strip()
    if not text:
        return None, make_error(400, "text required")
    if len(text) > MAX_SHARED_TEXT_CHARS:
        return None, make_error(
            413,
            "This text is too long to read as a message. "
            "Share a link to it instead, or a shorter part.",
        )
    return text, None


def _readable_language(code):
    """The Language for a code Zeeguu can read, else None."""
    if code not in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
        return None
    return Language.find_or_create(code)


def guess_language(text, learned_language):
    """
    The language of a shared message. The learner's own learned language
    unless langdetect is confident it is another language Zeeguu can read.
    Chat messages are short, and a wrong confident switch is worse than
    staying in the language the learner most likely shared it for.
    """
    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return learned_language
    if not candidates:
        return learned_language

    if learned_language and any(
        c.lang == learned_language.code and c.prob >= _LEARNED_LANGUAGE_CANDIDATE_FLOOR
        for c in candidates
    ):
        return learned_language
    best = candidates[0]
    if best.prob < _MIN_CONFIDENCE_TO_OVERRIDE:
        return learned_language
    return _readable_language(best.lang) or learned_language


def tokenize_for_reader(text, language):
    """
    One tokenized block per line of the message, as the article reader gets
    one per fragment. Chat messages break lines with a single newline (a list
    of times, "Husk:" and what to bring), which the tokenizer would merge.
    """
    from zeeguu.core.tokenization import TOKENIZER_MODEL, get_tokenizer

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
    if hasattr(tokenizer, "tokenize_batch"):
        return tokenizer.tokenize_batch(lines, flatten=False)
    return [tokenizer.tokenize_text(line, flatten=False) for line in lines]


def translate_whole_text(text, from_lang_code, to_lang_code):
    """The whole message in the learner's language, or None."""
    from python_translators.translation_query import TranslationQuery
    from zeeguu.core.translation_services.translator import get_next_results

    data = {
        "from_lang_code": from_lang_code,
        "to_lang_code": to_lang_code,
        "word": text,
        "query": TranslationQuery.for_word_occurrence(text, "", 1, 7),
        "context": "",
    }
    translations = get_next_results(data, number_of_results=1).translations
    if not translations:
        return None
    return translations[0]["translation"]


# ---------------------------------------------------------------------------
@api.route("/shared_text/prepare", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def shared_text_prepare():
    """
    form: text, and optionally language (a code) when the learner corrected
    the guessed one.

    Returns the language and, for each line of the text, its tokens as the
    reader expects them (paragraphs -> sentences -> tokens). Nothing is stored.
    """
    text, error = _shared_text_or_error()
    if error:
        return error

    user = User.find_by_id(flask.g.user_id)
    requested = request.form.get("language")
    if requested:
        language = _readable_language(requested)
        if not language:
            return make_error(406, f"Zeeguu can't read texts in '{requested}' yet.")
    else:
        language = guess_language(text, user.learned_language)

    return json_result(
        {
            "text": text,
            "language": language.code,
            "tokenized_lines": tokenize_for_reader(text, language),
        }
    )


# ---------------------------------------------------------------------------
@api.route("/shared_text/translate/<from_lang_code>/<to_lang_code>", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def shared_text_translate(from_lang_code, to_lang_code):
    """The whole shared message translated, for when single words aren't enough."""
    text, error = _shared_text_or_error()
    if error:
        return error

    translation = translate_whole_text(text, from_lang_code, to_lang_code)
    if translation is None:
        return make_error(502, "Could not translate this message right now.")
    return json_result({"translation": translation})
