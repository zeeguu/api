"""
Ask an LLM again when it answered in the wrong language.

The detection lives next door in ``language_check``; this is what to do about it
— re-prompt with the specific failure named, and give up after a bounded number
of tries. It is the only part of the language machinery that knows an LLM is
involved, which is why it is not in the detector.

What to do when it gives up is the *call site's* policy, and it differs: drop the
summary and keep the assessment, fail the whole simplification run, return None
and let the caller cope. So this raises, carrying enough for any of those.
"""

from zeeguu.core.language.language_check import (
    describe_mismatches,
    field_mismatches,
    log_mismatches,
)
from zeeguu.core.language.language_codes import language_name


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
