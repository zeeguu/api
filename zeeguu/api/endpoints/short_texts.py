"""
Short texts a learner brings to read word by word: a WhatsApp message, a
paragraph from a mail, pasted or shared from another app.

Stored once as a ShortText (deduplicated through Source, tokens kept) and
listed per learner in UserShortText; see
zeeguu/core/model/short_text.py. Taps go
through /translate_word like any other, with the text's source_id and the
ShortText context type, so a reopened text shows the words tapped before.
"""

import flask
from flask import request
from langdetect import detect_langs
from langdetect.lang_detect_exception import LangDetectException

from zeeguu.api.utils.abort_handling import make_error
from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import Bookmark, ShortText, User, UserShortText
from zeeguu.logging import log
from zeeguu.core.model.language import Language

from . import api, db_session

# A chat message, or a few forwarded together. Longer than this is an article
# pasted into a chat, and the reader for those is the article flow.
MAX_SHORT_TEXT_CHARS = 5000

# Below this, langdetect's guess is too often wrong to override the language
# the learner is learning: "Ok", "Tak!", a name and an emoji.
_MIN_CONFIDENCE_TO_OVERRIDE = 0.9

# If the learned language is among langdetect's candidates at all, keep it.
# Close languages split the vote: a Danish message often comes back as mostly
# Norwegian with some Danish, and the Danish learner meant Danish.
_LEARNED_LANGUAGE_CANDIDATE_FLOOR = 0.1


def _text_or_error():
    text = (request.form.get("text") or "").strip()
    if not text:
        return None, make_error(400, "text required")
    if len(text) > MAX_SHORT_TEXT_CHARS:
        return None, make_error(
            413,
            "This text is too long to read as a short text. "
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
    The language of a short text. The learner's own learned language unless
    langdetect is confident it is another language Zeeguu can read. Chat
    messages are short, and a wrong confident switch is worse than staying in
    the language the learner most likely brought it for.
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
    The text as InteractiveText reads it: one paragraph per line, sentences
    numbered across the whole text. Chat messages break lines with a single
    newline (a list of times, "Husk:" and what to bring), which the tokenizer
    would merge; and bookmarks are found again by (sentence, token), so the
    sentence numbers must not restart on each line.
    """
    from zeeguu.core.tokenization import TOKENIZER_MODEL, get_tokenizer

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
    if hasattr(tokenizer, "tokenize_batch"):
        tokenized_lines = tokenizer.tokenize_batch(lines, flatten=False)
    else:
        tokenized_lines = [tokenizer.tokenize_text(line, flatten=False) for line in lines]

    paragraphs = []
    sentences_before = 0
    for line_i, tokenized_line in enumerate(tokenized_lines):
        sentences = [sentence for paragraph in tokenized_line for sentence in paragraph]
        for sentence_i, sentence in enumerate(sentences):
            for token in sentence:
                token["sent_i"] = sentences_before + sentence_i
                token["paragraph_i"] = line_i
        sentences_before += len(sentences)
        paragraphs.append(sentences)

    return _with_mwes(paragraphs, language)


def _with_mwes(paragraphs, language):
    # The multi-word expressions the article reader groups (e.g. Danish
    # particle verbs), detected the way article fragments are. Fails open:
    # tapping still works word by word without them.
    from zeeguu.core.mwe import enrich_tokens_with_mwe

    try:
        return enrich_tokens_with_mwe(paragraphs, language.code)
    except Exception as e:
        log(f"[SHORT-TEXT] MWE detection failed, reading without: {e}")
        return paragraphs


def _users_short_text_or_404(user, short_text_id):
    # Only learners who brought a text can read it: it is often someone
    # else's message, never public.
    row = UserShortText.find(user, short_text_id)
    if not row:
        flask.abort(404, "Text not found")
    return row


# ---------------------------------------------------------------------------
@api.route("/short_texts", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def short_text_add():
    """
    form: text; optionally language (a code), when the learner corrected the
    guess, and instead_of (an id), the text read in the wrong language, which
    leaves the learner's list.

    Returns {id}; the reader then opens it with GET /short_texts/<id>.
    """
    text, error = _text_or_error()
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
        if not language:
            # No learned language to fall back on, and no confident guess
            return make_error(406, "Couldn't tell the language of this text.")

    short_text = ShortText.find_or_create(db_session, text, language)
    UserShortText.add(db_session, user, short_text)

    instead_of = request.form.get("instead_of", type=int)
    if instead_of and instead_of != short_text.id:
        replaced = UserShortText.find(user, instead_of)
        if replaced:
            db_session.delete(replaced)

    db_session.commit()
    return json_result({"id": short_text.id})


# ---------------------------------------------------------------------------
@api.route("/short_texts", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def short_text_list():
    """The learner's short texts, most recently opened first."""
    user = User.find_by_id(flask.g.user_id)
    return json_result([row.as_list_item() for row in UserShortText.all_for(user)])


# ---------------------------------------------------------------------------
@api.route("/short_texts/<int:short_text_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def short_text_get(short_text_id):
    """
    The text for the reader: language, source_id, tokens (one paragraph per
    line) and the learner's past bookmarks in it.
    """
    user = User.find_by_id(flask.g.user_id)
    row = _users_short_text_or_404(user, short_text_id)
    UserShortText.add(db_session, user, row.short_text)  # back to the top of the list
    db_session.commit()

    short_text = row.short_text
    tokens = short_text.tokens(db_session, tokenize_for_reader)
    db_session.commit()
    return json_result(
        {
            "id": short_text.id,
            "text": short_text.content,
            "language": short_text.language.code,
            "source_id": short_text.source_id,
            "tokenized_paragraphs": tokens,
            "past_bookmarks": [
                each.to_json(True)
                for each in Bookmark.find_all_for_user_and_source(user, short_text.source)
            ],
        }
    )


# ---------------------------------------------------------------------------
@api.route("/short_texts/<int:short_text_id>", methods=["DELETE"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def short_text_forget(short_text_id):
    """
    Takes the text off the learner's list, and deletes it once no learner has
    it. Words learned from it stay.
    """
    user = User.find_by_id(flask.g.user_id)
    _users_short_text_or_404(user, short_text_id).forget(db_session)
    db_session.commit()
    return "OK"
