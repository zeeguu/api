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
from typing import Optional, List

from zeeguu.logging import log
from zeeguu.core.model.language import Language

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of combined translation validation and classification."""

    is_valid: bool
    corrected_word: Optional[str] = None  # If word should change
    corrected_translation: Optional[str] = None  # If translation is wrong
    frequency: Optional[str] = None  # unique/common/uncommon/rare
    phrase_type: Optional[str] = (
        None  # single_word/collocation/idiom/expression/arbitrary_multi_word
    )
    reason: Optional[str] = None  # Why it was fixed
    explanation: Optional[str] = None  # Extra context for learner (usage notes, nuances)
    literal_meaning: Optional[str] = None  # Word-by-word translation for idioms


class TranslationValidator:
    """Validates and classifies translations before they enter exercises."""

    MODEL_NAME = "claude-sonnet-4-5-20250929"

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
            # On error, assume valid with no classification (fail open)
            return ValidationResult(is_valid=True)

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
            # On error, return valid for all (fail open)
            return [ValidationResult(is_valid=True) for _ in items]

    def _parse_response(self, response_text: str) -> ValidationResult:
        """
        Parse LLM response into ValidationResult.

        Expected formats:
        - "VALID|frequency|phrase_type|explanation"
        - "FIX|corrected_word|corrected_translation|frequency|phrase_type|reason|explanation"
        """
        response_text = response_text.strip()
        parts = response_text.split("|")

        if parts[0].upper() == "VALID":
            if len(parts) >= 3:
                return ValidationResult(
                    is_valid=True,
                    frequency=parts[1].strip().lower() if len(parts) > 1 else None,
                    phrase_type=parts[2].strip().lower() if len(parts) > 2 else None,
                    explanation=parts[3].strip() if len(parts) > 3 and parts[3].strip() else None,
                    literal_meaning=parts[4].strip() if len(parts) > 4 and parts[4].strip() else None,
                )
            return ValidationResult(is_valid=True)

        if parts[0].upper() == "FIX":
            if len(parts) >= 5:
                return ValidationResult(
                    is_valid=False,
                    corrected_word=parts[1].strip() if parts[1].strip() else None,
                    corrected_translation=(
                        parts[2].strip() if parts[2].strip() else None
                    ),
                    frequency=parts[3].strip().lower() if len(parts) > 3 else None,
                    phrase_type=parts[4].strip().lower() if len(parts) > 4 else None,
                    reason=parts[5].strip() if len(parts) > 5 else None,
                    explanation=parts[6].strip() if len(parts) > 6 and parts[6].strip() else None,
                    literal_meaning=parts[7].strip() if len(parts) > 7 and parts[7].strip() else None,
                )
            elif len(parts) >= 3:
                # Partial response - at least word and translation
                return ValidationResult(
                    is_valid=False,
                    corrected_word=parts[1].strip() if parts[1].strip() else None,
                    corrected_translation=(
                        parts[2].strip() if parts[2].strip() else None
                    ),
                )

        # Unexpected format - log and assume valid
        log(f"Unexpected validation response format: {response_text}")
        logger.warning(f"Unexpected validation response format: {response_text}")
        return ValidationResult(is_valid=True)

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
                results.append(self._parse_response(lines[i]))
            else:
                # Missing line - assume valid
                results.append(ValidationResult(is_valid=True))

        return results

    # Backward compatibility - alias for old method name
    def validate_translation(
        self, word, translation, context, source_lang, target_lang
    ):
        """Alias for validate_and_classify for backward compatibility."""
        return self.validate_and_classify(
            word, translation, context, source_lang, target_lang
        )
