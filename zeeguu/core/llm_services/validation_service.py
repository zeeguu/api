"""
Centralized service for validating and fixing user word translations.

This service consolidates the validation logic that was previously duplicated in:
- four_levels_per_word.py (scheduling)
- generated_examples.py (API endpoint)
- prefetch_example_sentences_for_users.py (batch tool)

Usage:
    from zeeguu.core.llm_services.validation_service import UserWordValidationService

    # Returns the user_word to use (may be different if fixed), or None if unfixable
    user_word = UserWordValidationService.validate_and_fix(db_session, user_word)
"""

from typing import Optional
from zeeguu.logging import log


class UserWordValidationService:
    """Validates and fixes user_word translations before exercises."""

    # Enum string -> enum value mappings (defined once)
    @staticmethod
    def _get_frequency_map():
        from zeeguu.core.model.meaning import MeaningFrequency
        return {
            "unique": MeaningFrequency.UNIQUE,
            "common": MeaningFrequency.COMMON,
            "uncommon": MeaningFrequency.UNCOMMON,
            "rare": MeaningFrequency.RARE,
        }

    @staticmethod
    def _get_phrase_type_map():
        from zeeguu.core.model.meaning import PhraseType
        return {
            "single_word": PhraseType.SINGLE_WORD,
            "collocation": PhraseType.COLLOCATION,
            "idiom": PhraseType.IDIOM,
            "expression": PhraseType.EXPRESSION,
            "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD,
        }

    @classmethod
    def validate_and_fix(cls, db_session, user_word) -> Optional["UserWord"]:
        """
        Validate translation and fix if needed before exercises/examples.

        This prevents:
        - Wrong translations entering exercises
        - Wasted API calls generating examples for incorrect translations

        Args:
            db_session: Database session to use
            user_word: UserWord to validate

        Returns:
            UserWord to use (may be different if fixed), or None if unfixable/should skip
        """
        # Skip if already validated
        if user_word.meaning.validated != 0:
            return user_word

        # Get validator (fail gracefully if not available)
        try:
            from zeeguu.core.llm_services.translation_validator import TranslationValidator
            validator = TranslationValidator()
        except (ImportError, ValueError) as e:
            log(f"[VALIDATION] Skipping validation: {e}")
            return user_word

        # Get context from preferred bookmark
        bookmark = user_word.preferred_bookmark
        if not bookmark:
            log(f"[VALIDATION] No preferred bookmark for user_word {user_word.id}, skipping")
            return user_word

        context = bookmark.get_context()
        if not context:
            log(f"[VALIDATION] No context for user_word {user_word.id}, skipping")
            return user_word

        meaning = user_word.meaning

        log(f"[VALIDATION] Validating: '{meaning.origin.content}' -> '{meaning.translation.content}'")

        result = validator.validate_translation(
            word=meaning.origin.content,
            translation=meaning.translation.content,
            context=context,
            source_lang=meaning.origin.language.code,
            target_lang=meaning.translation.language.code
        )

        if result.is_valid:
            return cls._apply_valid_result(db_session, user_word, meaning, result, context)
        else:
            log(f"[VALIDATION] Translation needs fixing: {result.reason}")
            return cls._fix_bookmark(db_session, user_word, bookmark, result, context)

    @classmethod
    def _apply_valid_result(cls, db_session, user_word, meaning, result, context=None):
        """Apply validation result to a valid meaning."""
        from zeeguu.core.model.validation_log import ValidationLog

        log(f"[VALIDATION] Translation is valid")
        meaning.validated = 1

        # Set frequency and phrase_type from combined validation
        if result.frequency:
            freq_map = cls._get_frequency_map()
            meaning.frequency = freq_map.get(result.frequency)

        if result.phrase_type:
            type_map = cls._get_phrase_type_map()
            meaning.phrase_type = type_map.get(result.phrase_type)

        db_session.add(meaning)

        # Log the validation result
        ValidationLog.log_valid(
            db_session,
            meaning=meaning,
            user_word_id=user_word.id,
            context=context
        )

        db_session.commit()

        # Update fit_for_study in case phrase_type changed to arbitrary_multi_word
        user_word.update_fit_for_study(db_session)
        return user_word

    @classmethod
    def _fix_bookmark(cls, db_session, user_word, bookmark, validation_result, context=None):
        """
        Fix bookmark with corrected word/translation.

        Returns the new user_word to use, or None if unfixable.
        """
        from zeeguu.core.model import Meaning, UserWord
        from zeeguu.core.model.validation_log import ValidationLog
        from zeeguu.core.bookmark_operations.update_bookmark import (
            transfer_learning_progress,
            cleanup_old_user_word
        )

        old_meaning = user_word.meaning

        # Determine what to fix
        new_word = validation_result.corrected_word or old_meaning.origin.content
        new_translation = validation_result.corrected_translation or old_meaning.translation.content

        # If no actual correction was provided, mark as invalid but don't fix
        if new_word == old_meaning.origin.content and new_translation == old_meaning.translation.content:
            log(f"[VALIDATION] No correction provided, marking as invalid")
            old_meaning.validated = 2  # Invalid
            user_word.fit_for_study = False
            db_session.add_all([old_meaning, user_word])

            # Log the invalid result
            ValidationLog.log_invalid(
                db_session,
                meaning=old_meaning,
                user_word_id=user_word.id,
                reason=validation_result.reason,
                context=context
            )

            db_session.commit()
            return None

        log(f"[VALIDATION] Fixing: '{old_meaning.origin.content}' -> '{old_meaning.translation.content}'")
        log(f"[VALIDATION] To: '{new_word}' -> '{new_translation}'")

        # Create/find correct meaning
        new_meaning = Meaning.find_or_create(
            db_session,
            new_word,
            old_meaning.origin.language.code,
            new_translation,
            old_meaning.translation.language.code
        )
        new_meaning.validated = 1  # Mark as validated

        # Set frequency and phrase_type from validation result
        if validation_result.frequency:
            freq_map = cls._get_frequency_map()
            new_meaning.frequency = freq_map.get(validation_result.frequency)

        if validation_result.phrase_type:
            type_map = cls._get_phrase_type_map()
            new_meaning.phrase_type = type_map.get(validation_result.phrase_type)

        db_session.add(new_meaning)

        # Mark old meaning as invalid
        old_meaning.validated = 2  # Invalid/fixed
        db_session.add(old_meaning)

        # Log the fix
        ValidationLog.log_fixed(
            db_session,
            old_meaning=old_meaning,
            new_meaning=new_meaning,
            user_word_id=user_word.id,
            reason=validation_result.reason,
            context=context
        )

        # If meaning actually changed, update user's data
        if new_meaning.id != old_meaning.id:
            # Find or create UserWord for new meaning
            new_user_word = UserWord.find_or_create(
                db_session,
                user_word.user,
                new_meaning
            )

            # Transfer learning progress
            old_user_word = user_word
            transfer_learning_progress(db_session, old_user_word, new_user_word, bookmark)

            # Update bookmark to point to new user_word
            bookmark.user_word = new_user_word
            new_user_word.preferred_bookmark = bookmark
            db_session.add_all([bookmark, new_user_word])

            # Cleanup old user_word if orphaned
            cleanup_old_user_word(db_session, old_user_word, bookmark)

            db_session.commit()
            log(f"[VALIDATION] Fixed and moved to new UserWord {new_user_word.id}")
            return new_user_word
        else:
            # Same meaning (shouldn't happen often), just commit
            db_session.commit()
            log(f"[VALIDATION] Fixed translation, same meaning")
            return user_word
