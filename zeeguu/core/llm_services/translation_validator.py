"""
LLM-based translation validation and classification.

This service combines translation validation and meaning classification into
a single LLM call. It validates that the translation is correct for the specific
word (not influenced by idiomatic context), suggests corrections if needed,
and classifies frequency and phrase type.

Usage:
    from zeeguu.core.llm_services.translation_validator import TranslationValidator

    validator = TranslationValidator()
    result = validator.validate_and_classify(
        word="øjnene",
        translation="in the face",
        context="vi skal se virkeligheden i øjnene.",
        source_lang="Danish",
        target_lang="English"
    )
    # result.is_valid = False
    # result.corrected_word = "øjnene"
    # result.corrected_translation = "the eyes"
    # result.frequency = "common"
    # result.phrase_type = "single_word"
"""

import os
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

from zeeguu.logging import log
from zeeguu.core.model.language import Language
from zeeguu.core.llm_services import models

logger = logging.getLogger(__name__)


class ValidationOutcome(Enum):
    """What the LLM concluded — or that it never got to conclude anything."""

    VALID = "valid"  # LLM confirmed the translation
    INVALID = "invalid"  # LLM rejected it (with or without a correction)
    UNAVAILABLE = "unavailable"  # The check itself failed; we learned nothing


@dataclass
class ValidationResult:
    """Result of combined translation validation and classification."""

    outcome: ValidationOutcome
    corrected_word: Optional[str] = None  # If word should change
    corrected_translation: Optional[str] = None  # If translation is wrong
    frequency: Optional[str] = None  # unique/common/uncommon/rare
    cefr_level: Optional[str] = None  # A1/A2/B1/B2/C1/C2
    phrase_type: Optional[str] = (
        None  # single_word/collocation/idiom/expression/arbitrary_multi_word
    )
    reason: Optional[str] = None  # Why it was fixed
    explanation: Optional[str] = None  # Extra context for learner (usage notes, nuances)
    literal_meaning: Optional[str] = None  # Word-by-word translation for idioms

    @classmethod
    def unavailable(cls, reason: str) -> "ValidationResult":
        """The check could not be performed (API error, unparseable response)."""
        return cls(outcome=ValidationOutcome.UNAVAILABLE, reason=reason)

    @property
    def is_valid(self) -> bool:
        return self.outcome is ValidationOutcome.VALID

    @property
    def check_failed(self) -> bool:
        """True when no verdict was obtained — callers must not persist anything."""
        return self.outcome is ValidationOutcome.UNAVAILABLE


# --- Response layouts -------------------------------------------------------
#
# These mirror the pipe-delimited contracts declared in
# prompts/translation_validator.py. The single-call and batch prompts ask for
# DIFFERENT layouts (the batch prompt asks for no CEFR level), so each gets its
# own field list rather than sharing one positional parser.
#
# In both layouts every closed-vocabulary field (frequency / cefr_level /
# phrase_type) comes before every free-text field, so a stray "|" the model
# types inside an explanation or reason can never shift a field we validate.
_SINGLE_VALID_FIELDS = (
    "frequency", "cefr_level", "phrase_type", "explanation", "literal_meaning",
)
_SINGLE_FIX_FIELDS = (
    "corrected_word", "corrected_translation", "frequency", "cefr_level",
    "phrase_type", "reason", "explanation", "literal_meaning",
)
_BATCH_VALID_FIELDS = ("frequency", "phrase_type")
_BATCH_FIX_FIELDS = (
    "corrected_word", "corrected_translation", "frequency", "phrase_type", "reason",
)

_CEFR_LEVELS = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})

# The prompt's phrase-type vocabulary says "arbitrary_multi_word" but
# PhraseType.ARBITRARY_MULTI_WORD's value is "multi_word", so from_string()
# returns None for it. Without this alias every fragment the model correctly
# flags loses its phrase_type, and negative_qualities.exclude_because_multi_word
# never marks the word unfit for study.
_PHRASE_TYPE_ALIASES = {"arbitrary_multi_word": "multi_word"}


def _vocabularies():
    """Closed vocabularies, read from the enums so they cannot drift."""
    from zeeguu.core.model.meaning import MeaningFrequency, PhraseType

    return (
        frozenset(m.value for m in MeaningFrequency),
        frozenset(m.value for m in PhraseType),
    )


def _normalized_field(name, raw):
    """
    Clean one parsed field, or return None if it is absent or not interpretable.

    Values outside a closed vocabulary are dropped rather than stored: that is
    what a shifted line looks like (reason prose landing in phrase_type), and
    writing it through would corrupt the meaning row.
    """
    value = raw.strip()
    if not value:
        return None

    if name in ("frequency", "phrase_type"):
        frequencies, phrase_types = _vocabularies()
        value = value.lower()
        if name == "phrase_type":
            value = _PHRASE_TYPE_ALIASES.get(value, value)
        allowed = frequencies if name == "frequency" else phrase_types
    elif name == "cefr_level":
        value = value.upper()
        allowed = _CEFR_LEVELS
    else:
        return value  # free text: explanation / reason / corrected_* / literal_meaning

    if value not in allowed:
        log(f"Discarding out-of-vocabulary {name}: {value!r}")
        logger.warning(f"Discarding out-of-vocabulary {name}: {value!r}")
        return None
    return value


def _split_fields(line, field_names):
    """
    Map a pipe-delimited line onto `field_names`, skipping the leading tag.

    maxsplit is bounded by the layout so extra "|" characters are absorbed by
    the final (free-text) field instead of shifting every field after them.
    Trailing fields the model omitted are simply absent from the result.
    """
    values = line.split("|", len(field_names))[1:]
    parsed = {}
    for name, raw in zip(field_names, values):
        value = _normalized_field(name, raw)
        if value is not None:
            parsed[name] = value
    return parsed


class TranslationValidator:
    """Validates and classifies translations before they enter exercises."""

    MODEL_NAME = models.TRANSLATION_VALIDATION

    def __init__(self):
        """Initialize with Anthropic client."""
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key, timeout=30)

    def validate_and_classify(
        self,
        word: str,
        translation: str,
        context: str,
        source_lang: str,
        target_lang: str,
    ) -> ValidationResult:
        """
        Validate a translation and classify its frequency/phrase_type in one call.

        Args:
            word: The word that was translated
            translation: The current translation
            context: The sentence context where the word appeared
            source_lang: Source language code or name
            target_lang: Target language code or name

        Returns:
            ValidationResult with validation status, corrections, and classification
        """
        from .prompts.translation_validator import create_combined_validation_prompt

        # Convert language codes to names
        source_name = Language.LANGUAGE_NAMES.get(source_lang, source_lang)
        target_name = Language.LANGUAGE_NAMES.get(target_lang, target_lang)

        prompt = create_combined_validation_prompt(
            word=word,
            translation=translation,
            context=context,
            source_lang=source_name,
            target_lang=target_name,
        )

        try:
            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=200,
                temperature=0,  # Deterministic for validation
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text.strip()
            return self._parse_response(response_text)

        except Exception as e:
            log(f"Translation validation failed: {e}")
            logger.error(f"Translation validation failed: {e}")
            # No verdict. Report it as such rather than as VALID: a transient
            # API failure must not persist `validated = VALID` on a meaning
            # nobody actually checked.
            return ValidationResult.unavailable(f"validation call failed: {e}")

    def validate_and_classify_batch(self, items: List[dict]) -> List[ValidationResult]:
        """
        Validate and classify multiple translations in one API call.

        Args:
            items: List of dicts with keys: word, translation, context, source_lang, target_lang

        Returns:
            List of ValidationResult in same order as input
        """
        if not items:
            return []

        from .prompts.translation_validator import create_batch_validation_prompt

        # Convert language codes to names in items
        converted_items = []
        for item in items:
            converted_items.append(
                {
                    "word": item["word"],
                    "translation": item["translation"],
                    "context": item["context"],
                    "source_lang": Language.LANGUAGE_NAMES.get(
                        item["source_lang"], item["source_lang"]
                    ),
                    "target_lang": Language.LANGUAGE_NAMES.get(
                        item["target_lang"], item["target_lang"]
                    ),
                }
            )

        prompt = create_batch_validation_prompt(converted_items)

        try:
            # Estimate tokens: ~50 per response line
            max_tokens = len(items) * 60

            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text.strip()
            return self._parse_batch_response(response_text, len(items))

        except Exception as e:
            log(f"Batch validation failed: {e}")
            logger.error(f"Batch validation failed: {e}")
            # No verdict for any item — see validate_and_classify.
            return [
                ValidationResult.unavailable(f"batch validation call failed: {e}")
                for _ in items
            ]

    def _parse_response(self, response_text: str) -> ValidationResult:
        """Parse a single-call response (see _SINGLE_* layouts)."""
        return self._parse_line(
            response_text, _SINGLE_VALID_FIELDS, _SINGLE_FIX_FIELDS
        )

    def _parse_line(self, line, valid_fields, fix_fields) -> ValidationResult:
        """
        Parse one pipe-delimited verdict line against the given layout.

        The verdict token is position 0, so it is never shifted by a stray
        delimiter; only the fields after it need defending.
        """
        line = line.strip()
        if not line:
            return ValidationResult.unavailable("empty validation response")

        tag = line.split("|", 1)[0].strip().upper()

        if tag == "VALID":
            # A short line still carries a trustworthy verdict - keep it and
            # accept that classification was lost.
            return ValidationResult(
                outcome=ValidationOutcome.VALID, **_split_fields(line, valid_fields)
            )

        if tag == "FIX":
            fields = _split_fields(line, fix_fields)
            if not (fields.get("corrected_word") or fields.get("corrected_translation")):
                # "Invalid" with nothing to correct is not actionable, and
                # _fix_bookmark would read it as "no correction provided" and
                # permanently mark the meaning INVALID.
                return ValidationResult.unavailable(
                    f"FIX response carried no correction: {line!r}"
                )
            return ValidationResult(outcome=ValidationOutcome.INVALID, **fields)

        # Unexpected format - we cannot tell whether the translation is good.
        log(f"Unexpected validation response format: {line}")
        logger.warning(f"Unexpected validation response format: {line}")
        return ValidationResult.unavailable(f"unparseable validation response: {line!r}")

    def _parse_batch_response(
        self, response_text: str, expected_count: int
    ) -> List[ValidationResult]:
        """Parse batch response into list of ValidationResults."""
        lines = [line.strip() for line in response_text.split("\n") if line.strip()]

        # If line count doesn't match, log warning but process what we have
        if len(lines) != expected_count:
            log(f"Batch validation: Expected {expected_count} lines, got {len(lines)}")

        results = []
        for i in range(expected_count):
            if i < len(lines):
                results.append(
                    self._parse_line(lines[i], _BATCH_VALID_FIELDS, _BATCH_FIX_FIELDS)
                )
            else:
                # Missing line - no verdict for this item.
                results.append(
                    ValidationResult.unavailable(
                        f"batch response had {len(lines)} lines, expected {expected_count}"
                    )
                )

        return results

    # Backward compatibility - alias for old method name
    def validate_translation(
        self, word, translation, context, source_lang, target_lang
    ):
        """Alias for validate_and_classify for backward compatibility."""
        return self.validate_and_classify(
            word, translation, context, source_lang, target_lang
        )

    def are_translations_equivalent(
        self,
        word: str,
        translation1: str,
        translation2: str,
        source_lang: str,
        target_lang: str,
    ) -> bool:
        """
        Check if two translations of the same word are semantically equivalent.

        This is used to prevent duplicate words in exercises when a user has
        multiple translations that mean the same thing (e.g., "cancel" vs "to cancel").

        Args:
            word: The source word being translated
            translation1: First translation
            translation2: Second translation
            source_lang: Source language code or name
            target_lang: Target language code or name

        Returns:
            True if translations are semantically equivalent, False otherwise
        """
        from .prompts.translation_validator import create_semantic_equivalence_prompt

        # Quick check: if translations are identical (case-insensitive), they're equivalent
        if translation1.lower().strip() == translation2.lower().strip():
            return True

        # Convert language codes to names
        source_name = Language.LANGUAGE_NAMES.get(source_lang, source_lang)
        target_name = Language.LANGUAGE_NAMES.get(target_lang, target_lang)

        prompt = create_semantic_equivalence_prompt(
            word=word,
            translation1=translation1,
            translation2=translation2,
            source_lang=source_name,
            target_lang=target_name,
        )

        try:
            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text.strip().upper()
            return response_text == "YES"

        except Exception as e:
            log(f"Semantic equivalence check failed: {e}")
            logger.error(f"Semantic equivalence check failed: {e}")
            # On error, assume NOT equivalent (fail safe - don't skip words)
            return False
