"""
Verifies that text an LLM produced is actually in the language we asked for.

Every one of these failures is silent by construction: the pipeline succeeds, the
row is written, and it is usually cached and reused. An audio lesson comes back
entirely in English, a "Danish" summary reads as English, a translation is never
translated. Asking harder in the prompt lowers the rate; only checking the output
finds the residue.

The question this asks is **"is this plausibly Danish?"**, not "which language is
this?". That distinction is the whole design.

A detector that only names a winner forces a question nobody wants to answer. Ask
"which language is this?" of short Danish and it often says Norwegian, so the first
version carried a hand-maintained list of confusable families to decide that
Norwegian was close enough to Danish to allow. That list forgave real defects
along with the misreads: a Norwegian learner served a Danish script passed.

Asking about the expected language directly never raises the question. Correct
Danish scores 0.6-0.99 as Danish — no adjudication needed — and English in a
Danish lesson scores 0.01. Given enough text the neighbours separate cleanly too:
this Danish paragraph scores 4e-09 as Norwegian, so a script in the wrong
Scandinavian language is now caught rather than excused. Short lines are the only
place neighbours genuinely blur, and there the aggregation described below absorbs
it.

Measured over 6532 stored audio lessons: this flags 8 where the previous
langdetect implementation flagged 12, and the four it stops flagging were all
sound text (Dutch read as Afrikaans, mostly).

"Can't judge" remains a distinct answer from "wrong". Text too short to carry
signal, and languages with no model — Zeeguu offers Kurdish, lingua has no
Kurdish — must never block.

Detection is shared; *policy* is not. What to do about a mismatch differs per call
site, and the retrying lives in the sibling ``generate_in_language``. See
docs/future-work/llm-output-language-verification.md.
"""

import re
from collections import namedtuple

from lingua import IsoCode639_1, Language, LanguageDetectorBuilder

from zeeguu.core.language.language_codes import language_name
from zeeguu.logging import log

# How plausible the expected language must be, for one piece of text.
#
# Sized for text of a few sentences, which is what callers give it: a summary, an
# article body, or a group of lesson lines.
#
# Measured on a full production sweep with the drill echo removed, the two
# populations are further apart than anything else we tried: every genuinely
# wrong-language script scores 0.00, and the sound A1 lessons that a 0.30 floor
# caught by mistake — four short sentences of Swedish, Danish or German — score
# 0.22-0.26. Prose of any length scores far higher still. So this sits in the
# middle of a gap from 0.00 to 0.22 rather than shaving one edge of it, which is
# the mistake 0.2 and then 0.30 both made from the other side.
#
# It does NOT work on a single short sentence, and two production runs went wrong
# learning that. Correct short Danish scores 0.08-0.15 as Danish, because the
# Scandinavian languages divide the confidence among themselves, and wrong-language
# text scores 0.00-0.14. Those bands overlap: no floor separates them one sentence
# at a time. Callers whose unit is that small must group before asking — see
# LINES_PER_GROUP in script_language_validator.
GROUP_LEVEL_FLOOR = 0.15

# Below this many characters, a single text cannot be judged on its own — and
# nothing downstream will catch the error, because a field is checked alone.
# Measured: correct Danish scores 0.07 for "Vi ses" and 0.12 for "Er det i
# kantinen?", well under the floor. So titles and one-line summaries answer
# "can't judge", exactly as they did before.
#
# A lesson script is different: its lines are short by nature, and the lesson-level
# threshold in script_language_validator absorbs the odd bad one. That check sets
# its own, much lower, minimum — see MIN_WORDS_PER_LINE there.
MIN_CHARS_TO_JUDGE = 60

# Zeeguu spells some codes differently, and lingua splits Norwegian into Bokmål and
# Nynorsk. Without the 'no' mapping every Norwegian lesson would be unjudgeable.
_ZEEGUU_TO_ISO = {"no": "NB", "zh-CN": "ZH"}

LanguageMismatch = namedtuple(
    "LanguageMismatch",
    ["label", "expected", "detected", "expected_probability", "sample"],
)

_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def _detectable_text(text: str) -> str:
    """
    Strip markup and collapse whitespace. Anchored to a letter after the bracket
    so this leaves prose alone: an unanchored <[^>]+> turns "Hvis 5 < 10 og 20 >
    15" into "Hvis 5 15", quietly deleting the evidence.
    """
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def _iso(zeeguu_code: str):
    name = _ZEEGUU_TO_ISO.get(zeeguu_code, (zeeguu_code or "").upper())
    return getattr(IsoCode639_1, name, None)


def _language(zeeguu_code: str):
    """The lingua language for a Zeeguu code, or None when there is no model."""
    iso = _iso(zeeguu_code)
    if iso is None:
        return None
    try:
        return Language.from_iso_code_639_1(iso)
    except Exception:
        return None


def _candidates():
    """
    Every language Zeeguu offers that lingua can model.

    The candidate set has to be this wide. Narrowing it to the learner's two
    languages makes short lines easier to judge but hides the failure that
    matters most in practice: asked for Italian, the LLM wrote Spanish because
    the word was Spanish too. Scored against only {Italian, English}, Spanish
    lands on Italian and passes. Measured: that configuration missed every
    sibling-language failure in the corpus.
    """
    from zeeguu.core.model.language import Language as ZeeguuLanguage

    languages = {_language(code) for code in ZeeguuLanguage.LANGUAGE_NAMES}
    return sorted(languages - {None}, key=lambda language: language.name)


_detector = None


def _detector_for_all_languages():
    """Built once, lazily: ~19MB resident and 0.2ms a line thereafter."""
    global _detector
    if _detector is None:
        _detector = LanguageDetectorBuilder.from_languages(*_candidates()).build()
    return _detector


def plausibility(text, expected_zeeguu_code):
    """
    How plausible it is that `text` is in the expected language, 0.0 to 1.0.

    Returns None only when there is no model for that language. It does NOT
    decide whether the text is long enough to trust — that judgement belongs to
    the caller, because how much text is enough depends on whether anything
    downstream can absorb a wrong answer. Compare MIN_CHARS_TO_JUDGE here with
    MIN_WORDS_PER_LINE in the script validator.
    """
    expected = _language(expected_zeeguu_code)
    if expected is None:
        return None

    text = _detectable_text(text)
    if not text:
        return None

    return _detector_for_all_languages().compute_language_confidence(text, expected)


def detected_language_of(text) -> str:
    """The Zeeguu code this text reads as, for reporting. 'unknown' if nothing fits."""
    best = _detector_for_all_languages().detect_language_of(_detectable_text(text))
    return best.iso_code_639_1.name.lower() if best else "unknown"


def language_mismatch(text, expected_zeeguu_code, label="text"):
    """
    Return a LanguageMismatch if `text` isn't plausibly in the expected language,
    else None.

    None also means "can't judge": no model for the language, or too little text
    to stand on its own. Callers must not read it as proof the text is right.
    """
    if _language(expected_zeeguu_code) is None:
        # Genuinely unjudgeable, but a silent skip is indistinguishable from a
        # successful check — which is the failure mode this module exists for. Said
        # here rather than in plausibility() so a lesson logs once, not once a line.
        log(f"[language_check] no model to check {label!r} against: "
            f"{expected_zeeguu_code!r}")
        return None

    if len(_detectable_text(text)) < MIN_CHARS_TO_JUDGE:
        return None

    confidence = plausibility(text, expected_zeeguu_code)
    if confidence is None or confidence >= GROUP_LEVEL_FLOOR:
        return None

    return LanguageMismatch(
        label=label,
        expected=expected_zeeguu_code,
        detected=detected_language_of(text),
        expected_probability=confidence,
        sample=_detectable_text(text)[:120],
    )


def field_mismatches(fields, expected_zeeguu_code) -> list:
    """
    Check several labelled texts at once.

    Args:
        fields: [(label, text), ...] — one entry per thing a caller can drop
            independently (a summary, a CEFR level).
        expected_zeeguu_code: the language all of them should be in.

    Returns:
        A LanguageMismatch per wrong field; empty when everything looks right
        (or couldn't be judged).
    """
    mismatches = [
        language_mismatch(text, expected_zeeguu_code, label) for label, text in fields
    ]
    return [m for m in mismatches if m]


def describe_mismatches(mismatches: list) -> str:
    """One clause per mismatch, for logs and for telling the LLM what it got wrong."""
    return "; ".join(
        f"{m.label}: expected '{m.expected}' but reads as '{m.detected}' "
        f"(plausibility of '{m.expected}': {m.expected_probability:.2f}) — "
        f'e.g. "{m.sample}"'
        for m in mismatches
    )


def log_mismatches(context: str, mismatches: list) -> None:
    log(f"[language_check] {context}: {describe_mismatches(mismatches)}")


def correction_note(mismatches: list, expected_zeeguu_code: str) -> str:
    """
    The note appended to the prompt on a retry. Naming the specific fields that
    came back wrong works far better than repeating the original instruction.
    """
    name = language_name(expected_zeeguu_code)
    return (
        "\n\nYour previous attempt used the wrong language: "
        f"{describe_mismatches(mismatches)}.\n"
        f"Write it again, entirely in {name}. Translate everything — do not leave "
        "any part in the language of the previous attempt."
    )
