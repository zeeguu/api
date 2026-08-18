"""
Verifies that text an LLM produced is actually in the language we asked for.

Every one of these failures is silent by construction: the pipeline succeeds, the
row is written, and it is usually cached and reused. An audio lesson comes back
entirely in English, a "Danish" summary reads as English, a translation is never
translated. Asking harder in the prompt lowers the rate; only checking the output
finds the residue.

Three things here were calibrated against real lessons and articles, and are the
reason this is a shared module rather than a one-line ``detect(text) == code``:

- **A fixed detector seed.** langdetect samples internally; without it the same
  text passes on one call and fails on the next.
- **Confusable families.** langdetect routinely reads short Danish as Norwegian.
  The failure worth catching is a whole text in the wrong language, not a
  marginal misread, so any member of a family counts as evidence for the others.
- **"Can't judge" is a distinct answer from "wrong."** Under ~60 characters there
  isn't enough signal, and some languages Zeeguu offers (Kurdish, Serbian) have
  no langdetect profile at all. Neither may block.

Detection is shared; *policy* is not. What to do about a mismatch — retry, drop
the field, drop one level and keep the rest, discard the correction — differs per
call site, so this module only ever reports and (in ``generate_in_language``)
re-prompts. See docs/future-work/llm-output-language-verification.md.
"""

import re
from collections import namedtuple

from langdetect import detect_langs
from langdetect.detector_factory import DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from zeeguu.core.language.language_codes import language_name
from zeeguu.logging import log

# langdetect samples internally; without a fixed seed the same text can pass on
# one call and fail on the next.
DetectorFactory.seed = 0

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
# exactly what an A1/A2 text is made of — make this worse. We accept any member of
# the family as evidence for the expected language: the failure we're guarding
# against is "the Danish text came out in English", not "Danish scored as Norwegian".
_CONFUSABLE_FAMILIES = [
    {"da", "no", "sv"},
    {"hr", "sl", "mk", "bg"},
    {"es", "ca", "pt"},
    {"cs", "sk"},
    {"id", "tl"},
    {"hi", "mr", "ne"},
]

# Below this, the text is too short for langdetect to say anything meaningful.
# Titles and single-word translations sit under it and will always be "can't judge".
MIN_CHARS_FOR_DETECTION = 60

# Combined probability the expected language (plus its confusables) must reach.
MIN_EXPECTED_PROBABILITY = 0.5

LanguageMismatch = namedtuple(
    "LanguageMismatch",
    ["label", "expected", "detected", "expected_probability", "sample"],
)


class LanguageMismatchError(Exception):
    """
    Raised by ``generate_in_language`` when the LLM keeps answering in the wrong
    language.

    Carries ``.mismatches`` (which fields were wrong) and ``.result`` (the last
    thing generated), so callers whose policy is partial salvage — keep the
    assessment and drop the summary, keep five levels and drop the sixth — can
    act on it instead of losing everything.
    """

    def __init__(self, context, mismatches, result=None):
        super().__init__(f"{context}: {describe_mismatches(mismatches)}")
        self.context = context
        self.mismatches = mismatches
        self.result = result


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


_TAG = re.compile(r"<[^>]+>")


def _detectable_text(text: str) -> str:
    """Strip HTML tags and collapse whitespace — much of what we check is markup."""
    return re.sub(r"\s+", " ", _TAG.sub(" ", text or "")).strip()


def language_mismatch(text, expected_zeeguu_code, label="text"):
    """
    Return a LanguageMismatch if `text` isn't in the expected language, else None.

    None also means "can't judge": empty or short text, or a language langdetect
    has no profile for. Callers must not read None as proof the text is right.
    """
    expected = _langdetect_code(expected_zeeguu_code)
    if expected not in LANGDETECT_SUPPORTED:
        return None

    text = _detectable_text(text)
    if len(text) < MIN_CHARS_FOR_DETECTION:
        return None

    probabilities = _probabilities(text)
    if not probabilities:
        return None

    accepted = _accepted_codes(expected)
    expected_probability = sum(p for code, p in probabilities.items() if code in accepted)
    if expected_probability >= MIN_EXPECTED_PROBABILITY:
        return None

    return LanguageMismatch(
        label=label,
        expected=expected,
        detected=max(probabilities, key=probabilities.get),
        expected_probability=expected_probability,
        sample=text[:120],
    )


# A contiguous run this long in the wrong language is a real failure, not a misread.
PASSAGE_CHUNK_CHARS = 300

# How much of a text may be in the wrong language before the whole thing is wrong.
# A quoted foreign sentence inside an article is normal; half the dialogue is not.
MAX_WRONG_SHARE = 0.25


def _chunk(pieces, size=PASSAGE_CHUNK_CHARS) -> list:
    """Group consecutive pieces into blocks of roughly `size` characters."""
    chunks, current, length = [], [], 0
    for piece in pieces:
        piece = _detectable_text(piece)
        if not piece:
            continue
        current.append(piece)
        length += len(piece) + 1
        if length >= size:
            chunks.append(" ".join(current))
            current, length = [], 0
    if current:
        tail = " ".join(current)
        # Fold a short trailing block into the previous one rather than judge it alone.
        if chunks and len(tail) < size // 2:
            chunks[-1] += " " + tail
        else:
            chunks.append(tail)
    return chunks


def passage_mismatch(pieces, expected_zeeguu_code, label="text"):
    """
    Check a long text made of many pieces (voice lines, paragraphs) for a
    wrong-language *run*, and return a LanguageMismatch if one is big enough.

    ``language_mismatch`` judges a text as a single blob, which averages partial
    failures away — the case this exists for: a Danish lesson whose opening
    dialogue is entirely English but whose practice phrases are correctly Danish
    scores 71% Danish overall and passes, while the learner hears two solid
    minutes of English. Chunking finds the English half; the share threshold
    keeps a single quoted foreign sentence from failing an otherwise good text.
    """
    chunks = _chunk(pieces)
    if not chunks:
        return None
    if len(chunks) == 1:
        return language_mismatch(chunks[0], expected_zeeguu_code, label)

    wrong = [
        (chunk, mismatch)
        for chunk, mismatch in (
            (c, language_mismatch(c, expected_zeeguu_code, label)) for c in chunks
        )
        if mismatch
    ]
    if not wrong:
        return None

    wrong_chars = sum(len(c) for c, _ in wrong)
    share = wrong_chars / sum(len(c) for c in chunks)
    if share < MAX_WRONG_SHARE:
        return None

    worst = min(wrong, key=lambda pair: pair[1].expected_probability)[1]
    return worst._replace(label=f"{label} ({round(100 * share)}% of it)")


def field_mismatches(fields, expected_zeeguu_code) -> list:
    """
    Check several labelled texts at once.

    Args:
        fields: [(label, text), ...] — one entry per thing a caller can drop
            independently (a summary, a CEFR level, a group of voice lines).
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
        f"(confidence in '{m.expected}': {m.expected_probability:.2f}) — "
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


def generate_in_language(generate, expected_language, fields_of, context, attempts=2):
    """
    Call `generate` until what it produces is in `expected_language`.

    Args:
        generate: called as ``generate(correction)``. `correction` is "" on the
            first attempt and, after a mismatch, a note naming exactly what came
            back wrong — the caller appends it to its prompt.
        expected_language: Zeeguu language code, e.g. 'da'.
        fields_of: ``result -> [(label, text), ...]`` — the parts worth checking.
            One entry per independently droppable piece, so a caller returning a
            dict of CEFR levels can lose one level and keep the others.
        context: what is being generated, for logs and the raised error.
        attempts: total generations, including the first. Default 2 = one retry.

    Returns:
        The first result that passes the check.

    Raises:
        LanguageMismatchError, carrying the mismatches and the last result. What
        to do about it — drop a field, drop a level, return None, fail loudly —
        is the call site's policy, deliberately not decided here.
    """
    correction = ""
    result = None
    mismatches = []

    for attempt in range(1, attempts + 1):
        result = generate(correction)
        mismatches = field_mismatches(fields_of(result), expected_language)
        if not mismatches:
            return result
        log_mismatches(f"{context} (attempt {attempt}/{attempts})", mismatches)
        correction = correction_note(mismatches, expected_language)

    raise LanguageMismatchError(
        f"{context} came back in the wrong language {attempts} times",
        mismatches,
        result,
    )
