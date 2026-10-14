"""
Is another word the learner typed into a cloze also right?

The exercise expects the learner's own word ("synes"), but the prompt is its
translation ("thinks"), which other words fit too ("tænker", "mener"). Each
(meaning, typed word) is judged once by an LLM and stored in
meaning_alternative; a verdict the judge calls specific to its sentence is
reused for that sentence alone.

Sharing. Typed text goes into a prompt and its verdict into a cache, so it is
checked first (is_plausible_answer) and only reaches the model as delimited
data. A rejecting verdict is shared with everybody: being told "no" by mistake
costs one learner an exercise, and nobody gains by forging one. An accepting
verdict is shared only when the typed form is a known phrase of the language
(someone has met it while reading); otherwise it holds for the learner who
typed it alone. That keeps a single learner's odd input from making an answer
right for everybody, at the cost of judging rare-but-real words once per
learner until somebody reads them.
"""

import hashlib
import re

from sqlalchemy.exc import IntegrityError

from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.meaning_alternative import MeaningAlternative
from zeeguu.logging import log

# A word or a short phrase: the blank holds one or a few words. Anything else
# is wrong without asking anybody.
MAX_ALTERNATIVE_LENGTH = 40
MAX_ALTERNATIVE_WORDS = 4
# Letters (any script), joined by single spaces, apostrophes or hyphens:
# "tænker", "d'écran", "et stykke", "après-midi". No digits, quotes, brackets,
# newlines or other punctuation.
_PLAUSIBLE = re.compile(r"[^\W\d_]+(?:['’\- ][^\W\d_]+)*")

_OTHER_WHITESPACE = re.compile(r"[^\S ]")

UNKNOWN = "UNKNOWN"  # the judge could not be asked; the client treats it as wrong


def normalize(typed):
    return " ".join(typed.strip().lower().split())


def is_plausible_answer(alternative):
    return (
        0 < len(alternative) <= MAX_ALTERNATIVE_LENGTH
        and len(alternative.split()) <= MAX_ALTERNATIVE_WORDS
        and _PLAUSIBLE.fullmatch(alternative) is not None
    )


def blank_tokens(tokenized, sent_i, token_i, total_tokens):
    """
    The sentence rebuilt from its tokens (paragraphs -> sentences -> token
    dicts, as tokenize_for_reading makes them), with the tokens at
    (sent_i, token_i .. token_i + total_tokens - 1) replaced by one ___.
    None if no token is at that position.
    """
    pieces = []
    blanked = False
    last_target = token_i + total_tokens - 1
    for paragraph in tokenized:
        for sentence in paragraph:
            for token in sentence:
                in_target = token["sent_i"] == sent_i and token_i <= token["token_i"] <= last_target
                if in_target:
                    if not blanked:
                        pieces.append("___")
                        blanked = True
                    if token["token_i"] == last_target and token.get("has_space", True):
                        pieces.append(" ")
                    continue
                pieces.append(token["text"])
                if token.get("has_space", True):
                    pieces.append(" ")
    return "".join(pieces).strip() if blanked else None


def blank_bookmarked_word(session, bookmark):
    """
    The sentence as the learner saw it: the word they bookmarked (not just the
    first occurrence of its text) replaced by ___. None if it can't be placed,
    and then the answer is not judged: a judge that sees the expected word in
    the sentence judges nonsense.
    """
    from zeeguu.core.tokenization.word_position_finder import find_target_in_tokenized_context

    context = bookmark.context
    if not context:
        return None
    tokenized = context.get_tokenized(session=session)
    if not tokenized:
        return None

    # The bookmark's position is relative to its context; the tokens carry
    # positions in the article. Same arithmetic as Bookmark.as_dictionary.
    anchor = (
        (bookmark.sentence_i or 0) + (context.sentence_i or 0),
        (bookmark.token_i or 0) + (context.token_i or 0),
        bookmark.total_tokens or 1,
    )
    meaning = bookmark.user_word.meaning
    found = find_target_in_tokenized_context(
        meaning.origin.content, tokenized, meaning.origin.language, current_anchor=anchor
    )
    if not found:
        return None
    return blank_tokens(tokenized, *found)


def context_hash(context):
    return hashlib.sha256(context.strip().encode("utf-8")).hexdigest()


def is_known_phrase(alternative, language):
    """Somebody has met this form while reading: it is a real word or phrase
    of the language, not just something one learner typed."""
    from sqlalchemy import func

    from zeeguu.core.model import Phrase
    from zeeguu.core.model.db import db

    if db.engine.dialect.name == "sqlite":
        matches = func.lower(Phrase.content) == alternative
    else:
        matches = Phrase.content_lower == alternative
    return Phrase.query.filter(Phrase.language_id == language.id, matches).first() is not None


def judge_alternative(session, bookmark, typed, judge=None):
    """
    {"relation": SYNONYM | NEAR_SYNONYM_NOT_IDIOMATIC | NOT_SYNONYM | UNKNOWN,
     "explanation": str, "cached": bool}

    `judge` is a ClozeAlternativeJudge; tests pass a fake.
    """
    user_word = bookmark.user_word
    meaning = user_word.meaning
    expected = meaning.origin.content
    alternative = normalize(typed)

    if alternative == normalize(expected):
        # The client accepts exact matches itself; answer consistently anyway.
        return _verdict(MeaningAlternative.SYNONYM, "", cached=False)
    # Newlines and tabs would vanish in normalize(); an answer with them was
    # not a word for the blank anyway.
    if _OTHER_WHITESPACE.search(typed.strip()) or not is_plausible_answer(alternative):
        return _verdict(MeaningAlternative.NOT_SYNONYM, "", cached=False)

    sentence_hash = context_hash(bookmark.get_context())
    stored = MeaningAlternative.lookup(meaning.id, alternative, sentence_hash, user_word.user_id)
    if stored:
        return _verdict(stored.relation, stored.explanation or "", cached=True)

    try:
        blanked = blank_bookmarked_word(session, bookmark)
    except Exception as e:
        log(f"[CLOZE-ALTERNATIVE] could not blank bookmark {bookmark.id}: {e}")
        blanked = None
    if blanked is None:
        return _verdict(UNKNOWN, "", cached=False)

    try:
        if judge is None:
            from zeeguu.core.llm_services.cloze_alternative_judge import ClozeAlternativeJudge

            judge = ClozeAlternativeJudge()
        verdict = judge.judge(
            expected=expected,
            typed=alternative,
            translation=meaning.translation.content,
            blanked=blanked,
            source_lang=meaning.origin.language.code,
            target_lang=meaning.translation.language.code,
        )
    except Exception as e:
        log(f"[CLOZE-ALTERNATIVE] judge unavailable: {e}")
        verdict = None
    if verdict is None:
        return _verdict(UNKNOWN, "", cached=False)

    shared = verdict.relation == MeaningAlternative.NOT_SYNONYM or is_known_phrase(
        alternative, meaning.origin.language
    )
    _store(
        session,
        meaning,
        alternative,
        sentence_hash if verdict.context_specific else MeaningAlternative.GENERAL,
        None if shared else user_word.user_id,
        verdict,
        judge,
    )
    return _verdict(verdict.relation, verdict.explanation, cached=False)


def _store(session, meaning, alternative, stored_hash, user_id, verdict, judge):
    from zeeguu.core.llm_services.prompts.cloze_alternative import PROMPT_VERSION

    try:
        generator = AIGenerator.find_or_create(
            session,
            getattr(judge, "MODEL_NAME", "unknown"),
            PROMPT_VERSION,
            description="Judges other words typed into a cloze exercise",
        )
        session.add(
            MeaningAlternative(
                meaning_id=meaning.id,
                alternative=alternative,
                context_hash=stored_hash,
                user_id=user_id,
                relation=verdict.relation,
                explanation=verdict.explanation or None,
                ai_generator_id=generator.id,
            )
        )
        session.commit()
    except IntegrityError:
        # Another request stored the same verdict first; theirs stands.
        session.rollback()
    except Exception as e:
        # The learner still gets this verdict; it just isn't kept.
        session.rollback()
        log(f"[CLOZE-ALTERNATIVE] could not store '{alternative}' for meaning {meaning.id}: {e}")


def _verdict(relation, explanation, cached):
    return {"relation": relation, "explanation": explanation, "cached": cached}
