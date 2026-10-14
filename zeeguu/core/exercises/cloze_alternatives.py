"""
Is another word the learner typed into a cloze also right?

The exercise expects the learner's own word ("synes"), but the prompt is its
translation ("thinks"), which other words fit too ("tænker", "mener"). Each
(meaning, typed word) is judged once by an LLM and stored in
meaning_alternative for all learners; only a verdict the judge calls specific
to its sentence is reused for that sentence alone.
"""

import hashlib
import re

from sqlalchemy.exc import IntegrityError

from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.meaning_alternative import MeaningAlternative
from zeeguu.logging import log

# Longer than any word or short phrase: a sentence typed into the blank is
# wrong without asking anybody.
MAX_ALTERNATIVE_LENGTH = 60

UNKNOWN = "UNKNOWN"  # the judge could not be asked; the client treats it as wrong


def normalize(typed):
    return " ".join(typed.strip().lower().split())


def blank_out(context, expected):
    """The sentence as the learner saw it: the expected word replaced by ___."""
    pattern = re.compile(r"(?<!\w)" + re.escape(expected) + r"(?!\w)", re.IGNORECASE)
    blanked, n = pattern.subn("___", context, count=1)
    return blanked if n else context


def context_hash(context):
    return hashlib.sha256(context.strip().encode("utf-8")).hexdigest()


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

    if not alternative or len(alternative) > MAX_ALTERNATIVE_LENGTH:
        return _verdict(MeaningAlternative.NOT_SYNONYM, "", cached=False)
    if alternative == normalize(expected):
        # The client accepts exact matches itself; answer consistently anyway.
        return _verdict(MeaningAlternative.SYNONYM, "", cached=False)

    context = bookmark.get_context()
    sentence_hash = context_hash(context)

    stored = MeaningAlternative.lookup(meaning.id, alternative, sentence_hash)
    if stored:
        return _verdict(stored.relation, stored.explanation or "", cached=True)

    if judge is None:
        from zeeguu.core.llm_services.cloze_alternative_judge import ClozeAlternativeJudge

        judge = ClozeAlternativeJudge()

    verdict = judge.judge(
        expected=expected,
        typed=alternative,
        translation=meaning.translation.content,
        blanked=blank_out(context, expected),
        source_lang=meaning.origin.language.code,
        target_lang=meaning.translation.language.code,
    )
    if verdict is None:
        return _verdict(UNKNOWN, "", cached=False)

    _store(session, meaning, alternative, sentence_hash, verdict, judge)
    return _verdict(verdict.relation, verdict.explanation, cached=False)


def _store(session, meaning, alternative, sentence_hash, verdict, judge):
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
                context_hash=sentence_hash if verdict.context_specific else MeaningAlternative.GENERAL,
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
