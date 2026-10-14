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

import json
import os
import logging
from dataclasses import dataclass
from typing import Optional

from zeeguu.logging import log
from zeeguu.core.model.language import Language
from zeeguu.core.llm_services import models
from zeeguu.core.llm_services import claude

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of combined translation validation and classification."""

    is_valid: bool
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
    ) -> Optional[ValidationResult]:
        """
        Validate a translation and classify its frequency/phrase_type in one call.

        Args:
            word: The word that was translated
            translation: The current translation
            context: The sentence context where the word appeared
            source_lang: Source language code or name
            target_lang: Target language code or name

        Returns:
            ValidationResult with validation status, corrections, and classification,
            or None when no verdict could be had (API error, refusal, unparseable reply)
        """
        from .prompts.translation_validator import create_combined_validation_prompt, VALIDATION_SCHEMA

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
                **claude.request_options(self.MODEL_NAME),
                # Replies run ~200 tokens (max 266 on 50 prod cases). A cut-off
                # reply is unparseable JSON and gets no verdict, so leave room.
                max_tokens=1000,
                output_config={"format": {"type": "json_schema", "schema": VALIDATION_SCHEMA}},
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = claude.response_text(response).strip()
            return self._parse_response(response_text)

        except Exception as e:
            # No verdict is not a VALID verdict. Returning is_valid=True here
            # stamped every word "checked" for two weeks from 28 Sep 2026, when
            # an SDK change made every call raise. Report it so an outage shows
            # up in Sentry, and let the caller leave the word unvalidated.
            log(f"Translation validation failed: {e}")
            logger.error(f"Translation validation failed: {e}")
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            return None

    def _parse_response(self, response_text: str) -> ValidationResult:
        """ValidationResult from the reply, which the API holds to VALIDATION_SCHEMA.

        Empty strings are the schema's way of saying "not applicable"; they
        become None here, which is what callers read as absent.
        """
        reply = json.loads(response_text)

        def field(name):
            value = (reply.get(name) or "").strip()
            return value or None

        return ValidationResult(
            is_valid=reply["verdict"] == "VALID",
            corrected_word=None if reply["verdict"] == "VALID" else field("corrected_word"),
            corrected_translation=None if reply["verdict"] == "VALID" else field("corrected_translation"),
            frequency=field("frequency"),
            cefr_level=field("cefr"),
            phrase_type=field("phrase_type"),
            reason=field("reason"),
            explanation=field("explanation"),
            literal_meaning=field("literal_meaning"),
        )

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
                **claude.request_options(self.MODEL_NAME),
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = claude.response_text(response).strip().upper()
            return response_text == "YES"

        except Exception as e:
            log(f"Semantic equivalence check failed: {e}")
            logger.error(f"Semantic equivalence check failed: {e}")
            # On error, assume NOT equivalent (fail safe - don't skip words)
            return False
