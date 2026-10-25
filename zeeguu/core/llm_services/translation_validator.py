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
import re
from dataclasses import dataclass
from typing import Optional

from zeeguu.logging import log
from zeeguu.core.model.language import Language
from zeeguu.core.llm_services import models
from zeeguu.core.llm_services import claude
from zeeguu.core.llm_services.single_translation import lists_options, pick_one

logger = logging.getLogger(__name__)

# The model sometimes escapes a letter twice inside its JSON ("\\u0153"), so
# after json.loads the string still holds the six characters \u0153 instead
# of œ. Seen 14 Oct 2026: main-d'\u0153uvre, est soumis \u00e0, l'\u00e9poque.
LEFTOVER_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


@dataclass
class ValidationResult:
    """Result of combined translation validation and classification."""

    is_valid: bool
    # No card can be checked or fixed: broken sentence, or nothing fits
    is_unresolved: bool = False
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
    # The valid/corrected pair as a dictionary spells it: "Dette" at the
    # start of a sentence comes back as "dette"
    dictionary_word: Optional[str] = None
    dictionary_translation: Optional[str] = None
    # The reply's own sentence with the corrected card in place, for a FIX
    correction_in_sentence: Optional[str] = None
    # The reply's own judgement of its sentences (None when not given)
    card_in_sentence: Optional[str] = None
    card_reads_right: Optional[bool] = None
    correction_reads_right: Optional[bool] = None


def _words(text):
    # Curly and straight apostrophes are the same letter here: "don’t" = "don't"
    return re.findall(r"[\w']+", text.lower().replace("\u2019", "'"))


def words_in_order(phrase, sentence):
    """Are the words of `phrase` in `sentence`, in order, other words allowed
    between them? "put up for sale" is in "put their homes up for sale"; "mean"
    is not in "what it means to walk"."""
    remaining = iter(_words(sentence))
    return all(word in remaining for word in _words(phrase))


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
        from .prompts.translation_validator import (
            create_combined_validation_prompt,
            SINGLE_TRANSLATION_REMINDER,
            CARD_DOES_NOT_FIT_REMINDER,
            VALIDATION_SCHEMA,
        )

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
            result = self._ask(prompt, VALIDATION_SCHEMA)
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

        misfit = self._misfit(result, translation)
        if misfit:
            # The reply's own check says the card does not fit the sentence.
            # Ask once more with its own sentence in front of it; a card it
            # still cannot fit is not a card, so the word is given up on.
            card, sentence, problem = misfit
            try:
                result = self._ask(
                    prompt + CARD_DOES_NOT_FIT_REMINDER.format(card=card, sentence=sentence, problem=problem),
                    VALIDATION_SCHEMA,
                )
            except Exception as e:
                # As for the first call: no answer is no verdict, not a give-up
                log(f"Translation validation retry failed: {e}")
                return None
            misfit = self._misfit(result, translation)
            if misfit:
                from dataclasses import replace

                log(f"[VALIDATION] '{word}' = '{misfit[0]}' still does not fit its sentence; unresolved")
                return replace(
                    result,
                    is_valid=False,
                    is_unresolved=True,
                    corrected_word=None,
                    corrected_translation=None,
                    reason=(result.reason or "") + " [card still did not fit its sentence]",
                )

        if result.is_unresolved:
            return result

        if self._lists_options(result, word, translation):
            # The prompt already forbids "/" alternatives and glosses in
            # parentheses; ask once more about this very translation, so the
            # model, which sees the sentence, picks the option that fits.
            offending = result.corrected_translation or translation
            try:
                result = self._ask(
                    prompt + SINGLE_TRANSLATION_REMINDER.format(translation=offending),
                    VALIDATION_SCHEMA,
                )
            except Exception as e:
                # Keep the first reply and its classification; the fallback
                # below still reduces it to one option.
                log(f"Translation validation retry failed: {e}")

        if self._lists_options(result, word, translation):
            result = self._with_one_option(result, word, translation)
        return result

    def _ask(self, prompt, schema) -> "ValidationResult":
        response = self.client.messages.create(
            model=self.MODEL_NAME,
            **claude.request_options(self.MODEL_NAME),
            # Replies run ~200 tokens (max 266 on 50 prod cases). A cut-off
            # reply is unparseable JSON and gets no verdict, so leave room.
            max_tokens=1000,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(claude.response_text(response).strip())

    @staticmethod
    def _misfit(result, translation):
        """(card, sentence, problem) when the reply's own sentence check fails,
        else None: a card (the VALID one, or a FIX's correction) that the reply
        says does not read right in the sentence, or that is not even what the
        sentence it wrote says ("means" in the sentence, "mean" on the card)."""
        if result.is_unresolved:
            return None
        if result.is_valid:
            if result.card_reads_right is False:
                return translation, result.card_in_sentence, "You judged that this does not read right."
            # "what it means to walk" judged right, for the card "mean"
            if result.card_in_sentence and not words_in_order(translation, result.card_in_sentence):
                return translation, result.card_in_sentence, f'"{translation}" is not what that sentence says.'
            return None
        corrected = result.corrected_translation
        sentence = result.correction_in_sentence
        if not corrected or not sentence:
            return None
        if result.correction_reads_right is False:
            return corrected, sentence, "You judged that this does not read right."
        if not words_in_order(corrected, sentence):
            return corrected, sentence, f'"{corrected}" is not what that sentence says.'
        return None

    @staticmethod
    def _lists_options(result, word, translation):
        """Would the flashcard end up as "which must/which should" or
        "by (doing something)"? Checks the corrected translation of a FIX,
        and the current one of a VALID (old translations predate the rule)."""
        if result.is_valid:
            return lists_options(translation, word)
        # A FIX may correct only the word; the old translation then stays.
        return lists_options(
            result.corrected_translation or translation, result.corrected_word or word
        )

    @staticmethod
    def _with_one_option(result, word, translation):
        """Last resort when the model keeps listing options: keep the first
        one ourselves. A VALID becomes a FIX so the meaning gets replaced."""
        from dataclasses import replace

        source = translation if result.is_valid else (result.corrected_translation or translation)
        one = pick_one(source, result.corrected_word or word)
        if one == source:
            # Nothing we can safely drop ("(something)"): a FIX with the same
            # translation would only get the meaning marked invalid.
            log(f"[VALIDATION] '{source}' lists options but can't be reduced; leaving it")
            return result
        log(f"[VALIDATION] '{source}' lists options; keeping '{one}'")
        return replace(
            result,
            is_valid=False,
            corrected_translation=one,
            reason=(result.reason or "") + f" [kept one option of '{source}']",
        )

    @staticmethod
    def _parse_response(response_text: str) -> ValidationResult:
        """ValidationResult from the reply, which the API holds to VALIDATION_SCHEMA.

        Empty strings are the schema's way of saying "not applicable"; they
        become None here, which is what callers read as absent.
        """
        reply = json.loads(response_text)

        def field(name):
            value = (reply.get(name) or "").strip()
            value = LEFTOVER_UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), value)
            return value or None

        fixed = reply["verdict"] == "FIX"
        return ValidationResult(
            is_valid=reply["verdict"] == "VALID",
            is_unresolved=reply["verdict"] == "UNRESOLVED",
            corrected_word=field("corrected_word") if fixed else None,
            corrected_translation=field("corrected_translation") if fixed else None,
            frequency=field("frequency"),
            cefr_level=field("cefr"),
            phrase_type=field("phrase_type"),
            reason=field("reason"),
            explanation=field("explanation"),
            literal_meaning=field("literal_meaning"),
            dictionary_word=field("dictionary_word"),
            dictionary_translation=field("dictionary_translation"),
            correction_in_sentence=field("correction_in_sentence"),
            card_in_sentence=field("card_in_sentence"),
            card_reads_right=reply.get("card_reads_right"),
            correction_reads_right=reply.get("correction_reads_right") if fixed else None,
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
