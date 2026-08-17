"""
Verifies that a generated audio-lesson script is actually in the languages we asked for.

LLMs occasionally ignore the "Teacher speaks X, Man/Woman speak Y" instruction and
emit the whole script in one language — most visibly, a "Danish" lesson where the
dialogue is in English. The script is expensive to turn into audio and lands directly
in a user's daily lesson, so we check it before synthesis rather than after.
"""

from collections import namedtuple

from langdetect import detect_langs
from langdetect.detector_factory import DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from zeeguu.core.audio_lessons.script_parser import parse_script
from zeeguu.logging import log

# langdetect samples internally; without a fixed seed the same script can pass on one
# call and fail on the next.
DetectorFactory.seed = 0

# Which voices are expected to speak which language.
SOURCE_LANGUAGE_VOICES = {"teacher"}
TARGET_LANGUAGE_VOICES = {"teacherl2", "man", "woman", "armin", "aldo"}

# Zeeguu language codes that langdetect spells differently.
_ZEEGUU_TO_LANGDETECT = {
    "zh-CN": "zh-cn",
    "ind": "id",
}

# langdetect ships a profile per language; anything outside this set can't be checked.
# (Notably Zeeguu supports Kurdish and Serbian as native languages; langdetect doesn't.)
LANGDETECT_SUPPORTED = {
    "af", "ar", "bg", "bn", "ca", "cs", "cy", "da", "de", "el", "en", "es", "et",
    "fa", "fi", "fr", "gu", "he", "hi", "hr", "hu", "id", "it", "ja", "kn", "ko",
    "lt", "lv", "mk", "ml", "mr", "ne", "nl", "no", "pa", "pl", "pt", "ro", "ru",
    "sk", "sl", "so", "sq", "sv", "sw", "ta", "te", "th", "tl", "tr", "uk", "ur",
    "vi", "zh-cn", "zh-tw",
}

# Languages langdetect routinely mixes up with each other. Short, simple sentences —
# exactly what an A1/A2 lesson is made of — make this worse. We accept any member of
# the family as evidence for the expected language: the failure we're guarding against
# is "the Danish dialogue came out in English", not "Danish scored as Norwegian".
_CONFUSABLE_FAMILIES = [
    {"da", "no", "sv"},
    {"hr", "sl", "mk", "bg"},
    {"es", "ca", "pt"},
    {"cs", "sk"},
    {"id", "tl"},
    {"hi", "mr", "ne"},
]

# Below this, the joined text is too short for langdetect to say anything meaningful.
MIN_CHARS_FOR_DETECTION = 60

# Combined probability the expected language (plus its confusables) must reach.
MIN_EXPECTED_PROBABILITY = 0.5

LanguageMismatch = namedtuple(
    "LanguageMismatch", ["voices", "expected", "detected", "expected_probability", "sample"]
)


def _langdetect_code(zeeguu_code: str) -> str:
    return _ZEEGUU_TO_LANGDETECT.get(zeeguu_code, zeeguu_code.lower())


def _accepted_codes(code: str) -> set:
    """The expected code plus the languages langdetect tends to confuse it with."""
    for family in _CONFUSABLE_FAMILIES:
        if code in family:
            return set(family)
    return {code}


def _probabilities(text: str) -> dict:
    try:
        return {result.lang: result.prob for result in detect_langs(text)}
    except LangDetectException:
        return {}


def _check_group(voices, texts, expected_zeeguu_code):
    """Return a LanguageMismatch if this group of lines isn't in the expected language."""
    expected = _langdetect_code(expected_zeeguu_code)
    if expected not in LANGDETECT_SUPPORTED:
        return None

    text = " ".join(texts).strip()
    if len(text) < MIN_CHARS_FOR_DETECTION:
        return None

    probabilities = _probabilities(text)
    if not probabilities:
        return None

    accepted = _accepted_codes(expected)
    expected_probability = sum(p for code, p in probabilities.items() if code in accepted)
    if expected_probability >= MIN_EXPECTED_PROBABILITY:
        return None

    detected = max(probabilities, key=probabilities.get)
    return LanguageMismatch(
        voices=voices,
        expected=expected,
        detected=detected,
        expected_probability=expected_probability,
        sample=text[:120],
    )


def find_language_mismatches(script: str, target_language: str, source_language: str) -> list:
    """
    Check a lesson script against the languages it was supposed to be written in.

    Args:
        script: the raw script, with "Teacher:" / "Man:" / ... voice labels
        target_language: Zeeguu code of the language being learned (Man/Woman/TeacherL2)
        source_language: Zeeguu code of the learner's native language (Teacher)

    Returns:
        A list of LanguageMismatch — empty when the script looks right.
    """
    target_texts = []
    source_texts = []

    for voice_type, text, _ in parse_script(script):
        if voice_type in TARGET_LANGUAGE_VOICES:
            target_texts.append(text)
        elif voice_type in SOURCE_LANGUAGE_VOICES:
            source_texts.append(text)

    mismatches = [
        _check_group("Man/Woman/TeacherL2", target_texts, target_language),
        # When the learner's native language is the one being learned there is only
        # one language in play, and the teacher check would just repeat the first.
        _check_group("Teacher", source_texts, source_language)
        if source_language != target_language
        else None,
    ]
    return [m for m in mismatches if m]


def describe_mismatches(mismatches: list) -> str:
    """One-line-per-mismatch summary, for logs and for telling the LLM what it got wrong."""
    return "; ".join(
        f"the {m.voices} lines should be in '{m.expected}' but read as '{m.detected}' "
        f"(confidence in '{m.expected}': {m.expected_probability:.2f}) — e.g. \"{m.sample}\""
        for m in mismatches
    )


def log_mismatches(context: str, mismatches: list) -> None:
    log(f"[script_language_validator] {context}: {describe_mismatches(mismatches)}")
