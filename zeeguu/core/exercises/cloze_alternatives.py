"""
Is another answer the learner typed also right?

A cloze expects the learner's own word ("synes"), but the prompt is its
translation ("thinks"), which other words fit too ("tænker", "mener").
Likewise an exercise that asks for the translation expects the stored one
("look up" for "slå op"), and other translations are right too ("consult").
Each (meaning, language of the answer, typed answer) is judged once by an LLM
and stored in meaning_alternative; a verdict the judge calls specific to its
sentence is reused for that sentence alone.

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
# A translation may take a few more words ("to get rid of something").
MAX_TRANSLATION_LENGTH = 60
MAX_TRANSLATION_WORDS = 6
# Letters (any script), joined by single spaces, apostrophes or hyphens:
# "tænker", "d'écran", "et stykke", "après-midi". No digits, quotes, brackets,
# newlines or other punctuation.
_PLAUSIBLE = re.compile(r"[^\W\d_]+(?:['’\- ][^\W\d_]+)*")

_OTHER_WHITESPACE = re.compile(r"[^\S ]")

UNKNOWN = "UNKNOWN"  # the judge could not be asked; the client treats it as wrong


def normalize(typed):
    return " ".join(typed.strip().lower().split())


def is_plausible_answer(alternative, max_length=MAX_ALTERNATIVE_LENGTH, max_words=MAX_ALTERNATIVE_WORDS):
    return (
        0 < len(alternative) <= max_length
        and len(alternative.split()) <= max_words
        and _PLAUSIBLE.fullmatch(alternative) is not None
    )


def without_infinitive_to(answer, language):
    """English glosses of verbs come with and without "to" ("to look up",
    "look up"); either is the same answer. Mirrors the web's
    inputNormalization.withoutInfinitiveTo."""
    if language.code == "en" and answer.startswith("to "):
        return answer[3:].strip()
    return answer


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
    Another word typed into the cloze for this bookmark ("tænker" for "synes").

    {"relation": SYNONYM | NEAR_SYNONYM_NOT_IDIOMATIC | NOT_SYNONYM | UNKNOWN,
     "explanation": str, "cached": bool}

    `judge` is a ClozeAlternativeJudge; tests pass a fake.
    """
    return _judge_typed_answer(session, bookmark, typed, judge, of_translation=False)


def judge_translation_alternative(session, bookmark, typed, judge=None):
    """
    Another translation typed for this bookmark's word ("consult" for
    "slå op", where the stored translation is "look up"). Returns the same
    shape as judge_alternative.

    `judge` is a TranslationAlternativeJudge; tests pass a fake.
    """
    return _judge_typed_answer(session, bookmark, typed, judge, of_translation=True)


def _judge_typed_answer(session, bookmark, typed, judge, of_translation):
    user_word = bookmark.user_word
    meaning = user_word.meaning
    if of_translation:
        expected = meaning.translation.content
        language = meaning.translation.language
        limits = (MAX_TRANSLATION_LENGTH, MAX_TRANSLATION_WORDS)
    else:
        expected = meaning.origin.content
        language = meaning.origin.language
        limits = (MAX_ALTERNATIVE_LENGTH, MAX_ALTERNATIVE_WORDS)
    alternative = normalize(typed)

    if without_infinitive_to(alternative, language) == without_infinitive_to(normalize(expected), language):
        # The client accepts exact matches itself; answer consistently anyway.
        return _verdict(MeaningAlternative.SYNONYM, "", cached=False)
    # Newlines and tabs would vanish in normalize(); an answer with them was
    # not a word for the blank anyway.
    if _OTHER_WHITESPACE.search(typed.strip()) or not is_plausible_answer(alternative, *limits):
        return _verdict(MeaningAlternative.NOT_SYNONYM, "", cached=False)

    sentence = bookmark.get_context()
    sentence_hash = context_hash(sentence)
    stored = MeaningAlternative.lookup(meaning.id, language.id, alternative, sentence_hash, user_word.user_id)
    if stored:
        return _verdict(stored.relation, stored.explanation or "", cached=True)

    try:
        if judge is None:
            judge = _default_judge(of_translation)
        if of_translation:
            verdict = judge.judge(
                word=meaning.origin.content,
                expected=expected,
                typed=alternative,
                sentence=sentence,
                source_lang=meaning.origin.language.code,
                target_lang=language.code,
            )
        else:
            verdict = judge.judge(
                expected=expected,
                typed=alternative,
                translation=meaning.translation.content,
                sentence=sentence,
                source_lang=language.code,
                target_lang=meaning.translation.language.code,
            )
    except Exception as e:
        log(f"[CLOZE-ALTERNATIVE] judge unavailable: {e}")
        verdict = None
    if verdict is None:
        return _verdict(UNKNOWN, "", cached=False)

    shared = verdict.relation == MeaningAlternative.NOT_SYNONYM or is_known_phrase(alternative, language)
    _store(
        session,
        meaning,
        language,
        alternative,
        sentence_hash if verdict.context_specific else MeaningAlternative.GENERAL,
        None if shared else user_word.user_id,
        verdict,
        judge,
        of_translation,
    )
    return _verdict(verdict.relation, verdict.explanation, cached=False)


def _default_judge(of_translation):
    if of_translation:
        from zeeguu.core.llm_services.translation_alternative_judge import TranslationAlternativeJudge

        return TranslationAlternativeJudge()
    from zeeguu.core.llm_services.cloze_alternative_judge import ClozeAlternativeJudge

    return ClozeAlternativeJudge()


def _store(session, meaning, language, alternative, stored_hash, user_id, verdict, judge, of_translation):
    if of_translation:
        from zeeguu.core.llm_services.prompts.translation_alternative import PROMPT_VERSION

        description = "Judges other translations typed for a word in an exercise"
    else:
        from zeeguu.core.llm_services.prompts.cloze_alternative import PROMPT_VERSION

        description = "Judges other words typed into a cloze exercise"

    try:
        generator = AIGenerator.find_or_create(
            session,
            getattr(judge, "MODEL_NAME", "unknown"),
            PROMPT_VERSION,
            description=description,
        )
        session.add(
            MeaningAlternative(
                meaning_id=meaning.id,
                language_id=language.id,
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
