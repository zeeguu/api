"""
Centralized service for validating and fixing user word translations.

This service consolidates the validation logic that was previously duplicated in:
- four_levels_per_word.py (scheduling)
- generated_examples.py (API endpoint)
- prefetch_example_sentences_for_users.py (batch tool)

Validation outcomes:

| Scenario                                    | Outcome                                         |
|---------------------------------------------|-------------------------------------------------|
| Translation is valid                        | Mark VALID, return user_word                    |
| Invalid, no correction available            | Mark INVALID, fit_for_study=False, return None  |
| Invalid with correction -> different meaning| old=INVALID, new=VALID, transfer to new_user_word|
| Invalid with correction -> same meaning     | Mark VALID (semantic match), return user_word   |
| Duplicate meaning (same word, equiv. trans.)| Mark fit_for_study=False, return None           |
| Validator unavailable (error, refusal)      | Leave NOT_VALIDATED, return user_word           |

Usage:
    from zeeguu.core.llm_services.validation_service import UserWordValidationService

    # Returns the user_word to use (may be different if fixed), or None if unfixable
    user_word = UserWordValidationService.validate_and_fix(db_session, user_word)
"""

from dataclasses import replace
from typing import Optional
from zeeguu.core.model.study_choice import UnfitReason
from zeeguu.logging import log
from zeeguu.core.llm_services.translation_validator import BROKEN_SENTENCE, WORD_NOT_FIT


def _engine_of(user_word):
    """Who produced the pair being judged, for the validation log: the judged
    (preferred) bookmark's service, or else the user word's earliest bookmark
    that records one. The fallback is for when the preferred bookmark is a
    generated example sentence (example_contexts), which is a placement, not a
    translation, and records none."""
    from zeeguu.core.model.bookmark import Bookmark

    judged = user_word.preferred_bookmark
    if judged is not None and judged.translation_service_id is not None:
        return judged.translation_service_id
    first = (
        Bookmark.query.filter(
            Bookmark.user_word_id == user_word.id,
            Bookmark.translation_service_id.isnot(None),
        )
        .order_by(Bookmark.id)
        .first()
    )
    return first.translation_service_id if first else None


# A meaning judged in this many sentences without passing in one is given up
# on, so a word whose sentences are all bad costs a bounded number of calls.
MAX_SENTENCES_TRIED = 2


class UserWordValidationService:
    """Validates and fixes user_word translations before exercises."""

    @classmethod
    def check_for_duplicate_meaning(cls, db_session, user_word) -> bool:
        """
        Check if this user_word is a duplicate of another word the user is already learning or has learned.

        A duplicate means:
        - Same origin word (e.g., "ophæve")
        - User already has another UserWord for this origin that is:
          - Currently scheduled/being learned, OR
          - Already learned in the past
        - The translations are semantically equivalent (e.g., "cancel" vs "to cancel")

        If a duplicate is found, marks this user_word as fit_for_study=False.

        Returns:
            True if this is a duplicate (should not be scheduled), False otherwise
        """
        from zeeguu.core.model.user_word import UserWord
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
        from sqlalchemy import or_

        user = user_word.user
        origin_word = user_word.meaning.origin.content
        this_translation = user_word.meaning.translation.content

        # Find other UserWords for the same user with the same origin word
        # that are either being scheduled OR already learned
        other_user_words = (
            UserWord.query
            .outerjoin(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user.id)
            .filter(UserWord.id != user_word.id)
            .filter(
                or_(
                    BasicSRSchedule.id != None,  # Currently scheduled
                    UserWord.learned_time != None,  # Already learned
                )
            )
            .all()
        )

        # Filter to those with the same origin word (case-insensitive)
        same_origin_words = [
            uw for uw in other_user_words
            if uw.meaning.origin.content.lower() == origin_word.lower()
        ]

        if not same_origin_words:
            return False

        # Check if any of them have an equivalent translation
        try:
            from zeeguu.core.llm_services.translation_validator import TranslationValidator
            validator = TranslationValidator()
        except (ImportError, ValueError) as e:
            log(f"[DUPLICATE CHECK] Skipping: {e}")
            return False

        source_lang = user_word.meaning.origin.language.code
        target_lang = user_word.meaning.translation.language.code

        for other_uw in same_origin_words:
            other_translation = other_uw.meaning.translation.content

            if validator.are_translations_equivalent(
                word=origin_word,
                translation1=this_translation,
                translation2=other_translation,
                source_lang=source_lang,
                target_lang=target_lang,
            ):
                log(
                    f"[DUPLICATE CHECK] UserWord {user_word.id} ('{origin_word}' -> '{this_translation}') "
                    f"is equivalent to UserWord {other_uw.id} (-> '{other_translation}'). "
                    f"Marking as unfit for study."
                )
                user_word.unfit_reason = UnfitReason.DUPLICATE_MEANING
                user_word.fit_for_study = False
                db_session.add(user_word)
                db_session.commit()
                return True

        return False

    @classmethod
    def validate_and_fix(
        cls, db_session, user_word, sentences_tried=(), bookmark=None, recheck=False
    ) -> Optional["UserWord"]:
        """
        Validate translation and fix if needed before exercises/examples.

        This prevents:
        - Wrong translations entering exercises
        - Wasted API calls generating examples for incorrect translations

        Args:
            db_session: Database session to use
            user_word: UserWord to validate
            bookmark: the sentence to judge in; the preferred bookmark if None
            recheck: judge a meaning already VALID too (a learner reported it)

        Returns:
            UserWord to use (may be different if fixed), or None if unfixable/should skip
        """
        from zeeguu.core.model.meaning import Meaning

        # Skip if already validated as correct
        if user_word.meaning.validated == Meaning.VALID and not recheck:
            return user_word

        # Get validator (fail gracefully if not available)
        try:
            from zeeguu.core.llm_services.translation_validator import TranslationValidator
            validator = TranslationValidator()
        except (ImportError, ValueError) as e:
            log(f"[VALIDATION] Skipping validation: {e}")
            return user_word

        # Get context from preferred bookmark
        bookmark = bookmark or user_word.preferred_bookmark
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

        if result is None:
            # The validator could not answer. Keep the word NOT_VALIDATED, which
            # is what tools/validate_scheduled_meanings.py picks up; the
            # exercise goes on meanwhile. Scheduling validates only once, before
            # the first schedule, so it will not retry by itself.
            log(f"[VALIDATION] No verdict for user_word {user_word.id}, left unvalidated")
            return user_word

        if result.is_valid:
            return cls._apply_valid_result(db_session, user_word, meaning, result, context)
        elif bookmark.translation_source == "generated_example" or result.gave_up == BROKEN_SENTENCE:
            return cls._try_another_sentence(db_session, user_word, bookmark, result, sentences_tried, recheck)
        elif result.gave_up:
            return cls._give_up(db_session, user_word, meaning, result, context)
        else:
            log(f"[VALIDATION] Translation needs fixing: {result.reason}")
            return cls._fix_bookmark(db_session, user_word, bookmark, result, context)

    @classmethod
    def _try_another_sentence(cls, db_session, user_word, bookmark, result, sentences_tried, recheck=False):
        """The meaning did not pass in this sentence, and the sentence is what
        is wrong: a generated example (anything but VALID), or a sentence the
        validator calls broken (BROKEN_SENTENCE).

        A generated example was generated for the meaning, so a FIX there must
        not change what the learner studies ("selv" = "even" must not become
        "selv om" because one example used "selv om"); the example is recorded
        and not used again. A broken sentence says nothing about the word,
        which may fit any other sentence. Either way the meaning is judged
        again in another sentence: a whole sentence of the learner's own
        (never a reader fragment, which is context for the meaning, not for
        study), or else the next unused example. When the learner's own
        sentence was the broken one, examples only. With no sentence left, or
        after MAX_SENTENCES_TRIED, the word is given up on. Returns what validate_and_fix returns for the
        sentence the meaning is finally judged in.
        """
        from zeeguu.core.exercises.example_contexts import is_fragment, next_unused_example_bookmark
        from zeeguu.core.model.example_sentence import ExampleSentence
        from zeeguu.core.model.example_sentence_context import ExampleSentenceContext
        from zeeguu.core.model.example_sentence_misfit import ExampleSentenceMisfit

        log(f"[VALIDATION] Meaning of user_word {user_word.id} not judged in bookmark {bookmark.id} "
            f"({result.verdict}: {result.reason}); trying another sentence")
        if bookmark.translation_source == "generated_example":
            # .first(), not find_by_bookmark's .one(): a bookmark can carry
            # more than one example link
            example_context = ExampleSentenceContext.query.filter(
                ExampleSentenceContext.bookmark_id == bookmark.id
            ).first()
            example = example_context.example_sentence if example_context else ExampleSentence.query.filter(
                ExampleSentence.meaning_id == user_word.meaning_id,
                ExampleSentence.sentence == bookmark.get_context(),
            ).first()
            if example:
                ExampleSentenceMisfit.mark(db_session, example, f"{result.verdict}: {result.reason or ''}".strip())

        tried = sentences_tried + (bookmark.id,)
        next_sentence = None
        own_sentence_broken = (
            result.gave_up == BROKEN_SENTENCE and bookmark.translation_source != "generated_example"
        )
        if len(tried) < MAX_SENTENCES_TRIED:
            own = [] if own_sentence_broken else [
                b for b in user_word.bookmarks()
                if b.id not in tried
                and b.translation_source != "generated_example"
                and b.get_context()
                and not is_fragment(b)
            ]
            next_sentence = own[0] if own else next_unused_example_bookmark(db_session, user_word, skip_ids=tried)
        if not next_sentence:
            db_session.commit()
            # No sentence left that the meaning passes in: a FIX in an example
            # gives up as WORD_NOT_FIT, a broken sentence as itself
            gave_up = replace(result, is_valid=False, gave_up=result.gave_up or WORD_NOT_FIT)
            return cls._give_up(db_session, user_word, user_word.meaning, gave_up, bookmark.get_context())

        user_word.preferred_bookmark = next_sentence
        db_session.add(user_word)
        db_session.commit()
        return cls.validate_and_fix(db_session, user_word, tried, recheck=recheck)

    @classmethod
    def _give_up(cls, db_session, user_word, meaning, result, context=None):
        """The validator gave up on the meaning in this sentence: the sentence
        is broken (BROKEN_SENTENCE), or no meaning of the word fits it
        (WORD_NOT_FIT). Neither says the meaning is wrong for other learners,
        whose words on it are judged in their own sentences, so the meaning is
        left as it is - and is not logged in validation_log, which records
        what happened to meanings - and only this learner's word leaves study.
        Not for good, and not through study_choice, which is the learner's
        choice: when the learner does something with the word again (looks it
        up in a new sentence, stars it), fit_for_study is recomputed and the
        word is judged again, which after a broken sentence is what it needs.
        Commits. Returns None."""
        log(f"[VALIDATION] Gave up on user_word {user_word.id} in {context!r}: "
            f"[{result.gave_up.lower()}] {result.reason}")
        user_word.set_unfit_for_study(db_session, UnfitReason.VALIDATOR_GAVE_UP)
        db_session.commit()
        return None

    @classmethod
    def _apply_valid_result(cls, db_session, user_word, meaning, result, context=None):
        """Apply validation result to a valid meaning."""
        from zeeguu.core.model.validation_log import ValidationLog
        from zeeguu.core.model.meaning import Meaning, MeaningFrequency, PhraseType

        log(f"[VALIDATION] Translation is valid")
        meaning.validated = Meaning.VALID

        # Set frequency, phrase_type, and explanation from combined validation
        if result.frequency:
            meaning.frequency = MeaningFrequency.from_string(result.frequency)

        if result.phrase_type:
            meaning.phrase_type = PhraseType.from_string(result.phrase_type)

        if result.explanation:
            meaning.translation_explanation = result.explanation

        if result.literal_meaning:
            meaning.literal_meaning = result.literal_meaning

        meaning.take_case_from(db_session, result.dictionary_word, result.dictionary_translation)
        db_session.add(meaning)

        # Log the validation result
        ValidationLog.log_valid(
            db_session,
            meaning=meaning,
            user_word_id=user_word.id,
            context=context,
            translation_service_id=_engine_of(user_word),
        )

        db_session.commit()

        # Update fit_for_study in case phrase_type changed to arbitrary_multi_word
        user_word.update_fit_for_study(db_session)
        return user_word

    @classmethod
    def fix_with_verdict(cls, db_session, user_word, verdict):
        """
        Apply a FIX verdict reached elsewhere (the audio lesson check's
        pair-only verdict) exactly as validate_and_fix applies its own: the
        learner moves to the corrected pair with their progress, or, with no
        correction, becomes unfit for study, and the old meaning becomes
        INVALID. Other learners' words on it are judged in their own sentences
        by tools/validate_scheduled_meanings.py (nightly), as after any
        validator verdict. Commits. Returns the user word to use, or None.
        """
        # The verdict was reached in this bookmark's sentence: no sentence, no
        # verdict (script_generator._meaning_confirmed_wrong)
        bookmark = user_word.preferred_bookmark
        if not bookmark:
            log(f"[VALIDATION] No preferred bookmark for user_word {user_word.id}, cannot apply the fix")
            return None
        return cls._fix_bookmark(db_session, user_word, bookmark, verdict, bookmark.get_context())

    @classmethod
    def _fix_bookmark(cls, db_session, user_word, bookmark, validation_result, context=None):
        """
        Fix bookmark with corrected word/translation.

        Returns the new user_word to use, or None if unfixable.
        """
        from zeeguu.core.model import Meaning, UserWord
        from zeeguu.core.model.meaning import MeaningFrequency, PhraseType
        from zeeguu.core.model.translation_service import TranslationService
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
            old_meaning.validated = Meaning.INVALID
            user_word.unfit_reason = UnfitReason.VALIDATOR_INVALID
            user_word.fit_for_study = False
            db_session.add_all([old_meaning, user_word])

            # Log the invalid result
            ValidationLog.log_invalid(
                db_session,
                meaning=old_meaning,
                user_word_id=user_word.id,
                reason=validation_result.reason,
                context=context,
                translation_service_id=_engine_of(user_word),
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
        new_meaning.validated = Meaning.VALID

        # Set frequency, phrase_type, and explanation from validation result
        if validation_result.frequency:
            new_meaning.frequency = MeaningFrequency.from_string(validation_result.frequency)

        if validation_result.phrase_type:
            new_meaning.phrase_type = PhraseType.from_string(validation_result.phrase_type)

        if validation_result.explanation:
            new_meaning.translation_explanation = validation_result.explanation

        if validation_result.literal_meaning:
            new_meaning.literal_meaning = validation_result.literal_meaning

        new_meaning.take_case_from(
            db_session, validation_result.dictionary_word, validation_result.dictionary_translation
        )
        db_session.add(new_meaning)

        # If meaning actually changed, update user's data
        if new_meaning.id != old_meaning.id:
            # Mark old meaning as invalid (only if it's a different meaning!).
            # Also when the fix changed the word: on 2026-10-19 most of the 871
            # meanings marked by such fixes were broken pairs themselves
            # ('bruger den' → 'are using it', 'tenu' → 'tenuous'), and only
            # about a third were a fine word inside a bigger expression ('ud'
            # in 'ud af'), which then lose only their audio lessons.
            old_meaning.validated = Meaning.INVALID
            db_session.add(old_meaning)

            # Log the fix
            ValidationLog.log_fixed(
                db_session,
                old_meaning=old_meaning,
                new_meaning=new_meaning,
                user_word_id=user_word.id,
                reason=validation_result.reason,
                context=context,
                translation_service_id=_engine_of(user_word),
            )

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
            # Use ID to avoid circular dependency (Bookmark.user_word <-> UserWord.preferred_bookmark)
            bookmark.user_word_id = new_user_word.id
            bookmark.set_translation_service(db_session, TranslationService.VALIDATOR)
            db_session.add(bookmark)
            db_session.flush()  # Flush bookmark first

            new_user_word.preferred_bookmark_id = bookmark.id
            db_session.add(new_user_word)
            db_session.flush()
            # Judged with its sentence attached now: fit_for_study was worked
            # out when the word was created, or long before if it existed.
            # Expired so preferred_bookmark is reloaded from the id set above.
            db_session.expire(new_user_word, ["preferred_bookmark"])
            new_user_word.update_fit_for_study(db_session)

            # Cleanup old user_word if orphaned
            cleanup_old_user_word(db_session, old_user_word, bookmark)

            # Not orphaned when other bookmarks hold it, e.g. generated
            # examples placed for the wrong pair. Still fit, it was served
            # again and "fixed" again at every exercise: 108 words, 389
            # validator calls in Sep-Oct 2026, one word 35 times. Kept, since
            # the learner's look-ups stay anchored in what they read, but
            # excluded for good: REPLACED_BY_FIX is sticky. Its schedule
            # went to new_user_word with transfer_learning_progress.
            if old_user_word not in db_session.deleted:
                old_user_word.set_unfit_for_study(db_session, UnfitReason.REPLACED_BY_FIX)

            db_session.commit()
            log(f"[VALIDATION] Fixed and moved to new UserWord {new_user_word.id}")
            return new_user_word
        else:
            # Same meaning after case-insensitive lookup - LLM suggested case change
            # that resolved to same semantic meaning. Mark as valid (already done above).
            log(f"[VALIDATION] LLM suggested case change that resolved to same meaning - marking as valid")

            # Log as valid (not fixed, since meaning didn't actually change)
            ValidationLog.log_valid(
                db_session,
                meaning=new_meaning,
                user_word_id=user_word.id,
                context=context,
                translation_service_id=_engine_of(user_word),
            )

            db_session.commit()
            return user_word
