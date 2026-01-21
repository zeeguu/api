from .basicSR import ONE_DAY, BasicSRSchedule
from datetime import datetime, timedelta

MAX_LEVEL = 4

# Minimum delay before a word reappears in exercises.
# This gives users a clean "session complete" feeling instead of
# words immediately reappearing after wrong answers or level-ups.
MINIMUM_COOLING_INTERVAL = 30  # 30 minutes


# Levels can be 1,2,3,4
# When an old bookmark is migrated to the Levels scheduler the level is set to 0
# When a new bookmark is created and the user has the LevelsSR it's level is automatically set to 1
#


class FourLevelsPerWord(BasicSRSchedule):

    MAX_INTERVAL = 2 * ONE_DAY

    NEXT_COOLING_INTERVAL_ON_SUCCESS = {
        0: ONE_DAY,
        ONE_DAY: 2 * ONE_DAY,
    }

    # Reverse the process
    DECREASE_COOLING_INTERVAL_ON_FAIL = {
        v: k for k, v in NEXT_COOLING_INTERVAL_ON_SUCCESS.items()
    }
    # If at 0, we don't decrease it further.
    DECREASE_COOLING_INTERVAL_ON_FAIL[0] = 0

    def __init__(self, user_word=None, user_word_id=None):
        super(FourLevelsPerWord, self).__init__(user_word, user_word_id)

    def is_about_to_be_learned(self):
        level_before_this_exercises = self.user_word.level
        return (
            self.cooling_interval == self.MAX_INTERVAL
            and level_before_this_exercises == MAX_LEVEL
        )

    def update_schedule(self, db_session, correctness, exercise_time: datetime = None):

        if not exercise_time:
            exercise_time = datetime.now()

        level_before_this_exercises = self.user_word.level

        if correctness:
            # Update level for user_word or mark as learned
            self.consecutive_correct_answers += 1
            if self.cooling_interval == self.MAX_INTERVAL:
                if level_before_this_exercises < MAX_LEVEL:
                    self.user_word.level = level_before_this_exercises + 1
                    db_session.add(self.user_word)

                    # new exercise type can be done in the same day, thus cooling interval is 0
                    new_cooling_interval = 0

                else:
                    self.set_meaning_as_learned(db_session)
                    # we simply return because the self object will have been deleted inside of the above call
                    return
            else:
                # Correct, but we're staying on the same level
                new_cooling_interval = self.NEXT_COOLING_INTERVAL_ON_SUCCESS.get(
                    self.cooling_interval, self.MAX_INTERVAL
                )
        else:
            # correctness = FALSE
            # Decrease the cooling interval to the previous bucket
            new_cooling_interval = self.DECREASE_COOLING_INTERVAL_ON_FAIL[
                self.cooling_interval
            ]
            self.consecutive_correct_answers = 0

        # update next practice time
        self.cooling_interval = new_cooling_interval
        # Apply minimum delay so words don't reappear immediately
        # (but keep cooling_interval unchanged for progression logic)
        delay_minutes = max(new_cooling_interval, MINIMUM_COOLING_INTERVAL)
        next_practice_date = exercise_time + timedelta(minutes=delay_minutes)
        self.next_practice_time = next_practice_date

        db_session.add(self)

    @classmethod
    def get_max_interval(cls, in_days: bool = False):
        """
        in_days:bool False, use true if you want the interval in days, rather than
        minutes.
        :returns:int, total number of minutes the schedule can have as a maximum.
        """
        return cls.MAX_INTERVAL if not in_days else cls.MAX_INTERVAL // ONE_DAY

    @classmethod
    def get_cooling_interval_dictionary(cls):
        return cls.NEXT_COOLING_INTERVAL_ON_SUCCESS

    @classmethod
    def find_or_create(cls, db_session, user_word):

        schedule = super(FourLevelsPerWord, cls).find(user_word)

        if not schedule:
            # Validate translation before first schedule (if not already validated)
            if user_word.meaning.exercise_validated == 0:
                user_word = cls._validate_and_fix_if_needed(db_session, user_word)
                if user_word is None:
                    return None  # Validation failed, word is not fit for study

            # After validation, check if still fit for study
            if not user_word.fit_for_study:
                return None  # Don't create schedule for unfit words

            schedule = cls(user_word)
            user_word.level = 1
            db_session.add_all([schedule, user_word])
            db_session.commit()

        return schedule

    @classmethod
    def _validate_and_fix_if_needed(cls, db_session, user_word):
        """
        Validate translation and fix if needed before scheduling.

        Returns the user_word to use (may be different if fixed), or None if unfixable.
        """
        from zeeguu.logging import log

        try:
            from zeeguu.core.llm_services.translation_validator import TranslationValidator
            validator = TranslationValidator()
        except (ImportError, ValueError) as e:
            # API key not configured or module not available, skip validation
            log(f"[VALIDATION] Skipping validation: {e}")
            return user_word

        # Get context from preferred bookmark
        bookmark = user_word.preferred_bookmark
        if not bookmark:
            log(f"[VALIDATION] No preferred bookmark, skipping validation")
            return user_word

        context = bookmark.get_context()
        if not context:
            log(f"[VALIDATION] No context available, skipping validation")
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
            log(f"[VALIDATION] Translation is valid")
            meaning.exercise_validated = 1
            # Also set frequency and phrase_type from combined validation
            if result.frequency:
                from zeeguu.core.model.meaning import MeaningFrequency
                freq_map = {"unique": MeaningFrequency.UNIQUE, "common": MeaningFrequency.COMMON,
                           "uncommon": MeaningFrequency.UNCOMMON, "rare": MeaningFrequency.RARE}
                meaning.frequency = freq_map.get(result.frequency)
            if result.phrase_type:
                from zeeguu.core.model.meaning import PhraseType
                type_map = {"single_word": PhraseType.SINGLE_WORD, "collocation": PhraseType.COLLOCATION,
                           "idiom": PhraseType.IDIOM, "expression": PhraseType.EXPRESSION,
                           "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD}
                meaning.phrase_type = type_map.get(result.phrase_type)
            db_session.add(meaning)
            db_session.commit()
            # Update fit_for_study in case phrase_type changed to arbitrary_multi_word
            user_word.update_fit_for_study(db_session)
            return user_word
        else:
            log(f"[VALIDATION] Translation needs fixing: {result.reason}")
            return cls._fix_bookmark(db_session, user_word, bookmark, result)

    @classmethod
    def _fix_bookmark(cls, db_session, user_word, bookmark, validation_result):
        """
        Fix bookmark with corrected word/translation.

        Returns the new user_word to use, or None if unfixable.
        """
        from zeeguu.core.model import Meaning, UserWord
        from zeeguu.core.bookmark_operations.update_bookmark import (
            transfer_learning_progress,
            cleanup_old_user_word
        )
        from zeeguu.logging import log

        old_meaning = user_word.meaning

        # Determine what to fix
        new_word = validation_result.corrected_word or old_meaning.origin.content
        new_translation = validation_result.corrected_translation or old_meaning.translation.content

        # If no actual correction was provided, mark as invalid but don't fix
        if new_word == old_meaning.origin.content and new_translation == old_meaning.translation.content:
            log(f"[VALIDATION] No correction provided, marking as invalid")
            old_meaning.exercise_validated = 2  # Invalid
            user_word.fit_for_study = False
            db_session.add_all([old_meaning, user_word])
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
        new_meaning.exercise_validated = 1  # Mark as validated
        # Set frequency and phrase_type from validation result
        if validation_result.frequency:
            from zeeguu.core.model.meaning import MeaningFrequency
            freq_map = {"unique": MeaningFrequency.UNIQUE, "common": MeaningFrequency.COMMON,
                       "uncommon": MeaningFrequency.UNCOMMON, "rare": MeaningFrequency.RARE}
            new_meaning.frequency = freq_map.get(validation_result.frequency)
        if validation_result.phrase_type:
            from zeeguu.core.model.meaning import PhraseType
            type_map = {"single_word": PhraseType.SINGLE_WORD, "collocation": PhraseType.COLLOCATION,
                       "idiom": PhraseType.IDIOM, "expression": PhraseType.EXPRESSION,
                       "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD}
            new_meaning.phrase_type = type_map.get(validation_result.phrase_type)
        db_session.add(new_meaning)

        # Mark old meaning as invalid
        old_meaning.exercise_validated = 2  # Invalid/fixed
        db_session.add(old_meaning)

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
