from .basicSR import ONE_DAY, BasicSRSchedule
from datetime import datetime, timedelta

import sqlalchemy

from ...model import UserWord
from ...model.exercise_outcome import ExerciseOutcome

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
        # at level 4, the next correct answer learns the word if the word has
        # reached the longest interval, or (on the fast track) if it is clean
        return self.user_word.level == MAX_LEVEL and (
            self.cooling_interval == self.MAX_INTERVAL or self.is_on_fast_track()
        )

    def is_on_fast_track(self):
        """A clean answer now moves this word up a level: every answer at this
        level so far was clean, and the learner has fast progression."""
        return bool(self.fast_track) and self._fast_progression()

    def _fast_progression(self):
        return self.user_word.user.has_feature("fast_progression")

    def update_schedule(
        self, db_session, correctness, exercise_time: datetime = None, outcome=None
    ):

        if not exercise_time:
            exercise_time = datetime.now()

        level_before_this_exercises = self.user_word.level
        min_delay = MINIMUM_COOLING_INTERVAL
        moved_up = False

        if correctness:
            # Update level for user_word or mark as learned
            self.consecutive_correct_answers += 1
            # Fast progression: while every answer at this level has been clean
            # (first try, no hint), a clean answer is evidence enough to move up
            # now, instead of after three spaced correct answers.
            clean_and_fast = (
                outcome == ExerciseOutcome.CORRECT and self.is_on_fast_track()
            )
            if clean_and_fast or self.cooling_interval == self.MAX_INTERVAL:
                if level_before_this_exercises < MAX_LEVEL:
                    self.user_word.level = level_before_this_exercises + 1
                    db_session.add(self.user_word)
                    moved_up = True

                    # the new level starts from its first step
                    new_cooling_interval = 0
                    if clean_and_fast:
                        # fewer steps, same spacing: the next level waits for
                        # tomorrow. Only the practice date moves; the interval
                        # stays 0, so an answer with help later still needs
                        # all three steps at this level.
                        min_delay = ONE_DAY
                    # (otherwise the new exercise type can be done the same day)

                else:
                    self.set_meaning_as_learned(db_session)
                    from zeeguu.core import events
                    user_id = self.user_word.user.id
                    events.word_learned.send(None, user_id=user_id, db_session=db_session)
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

        # The fast track is per level: every level starts on it, and the first
        # answer at a level that is not clean takes the word off it until the
        # next level. "Listened" (an audio lesson) is not an answer, so it
        # changes nothing. Kept for every user, so the comparison group shows
        # which words would have stayed on it; only is_on_fast_track() needs
        # the feature.
        if moved_up:
            self.fast_track = True
        elif outcome is not None and outcome not in (
            ExerciseOutcome.CORRECT,
            ExerciseOutcome.LISTENED,
        ):
            self.fast_track = False

        # update next practice time
        self.cooling_interval = new_cooling_interval
        # Apply minimum delay so words don't reappear immediately
        # (but keep cooling_interval unchanged for progression logic)
        delay_minutes = max(new_cooling_interval, min_delay)
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
            # Validate translation before first schedule (if not already validated as correct)
            from zeeguu.core.model.meaning import Meaning
            if user_word.meaning.validated != Meaning.VALID:
                from zeeguu.core.llm_services.validation_service import UserWordValidationService
                user_word = UserWordValidationService.validate_and_fix(db_session, user_word)
                if user_word is None:
                    return None  # Validation failed, word is not fit for study

            # After validation, check if still fit for study
            if not user_word.fit_for_study:
                return None  # Don't create schedule for unfit words

            # Check for duplicate meanings (same word with equivalent translation already being learned)
            from zeeguu.core.llm_services.validation_service import UserWordValidationService
            if UserWordValidationService.check_for_duplicate_meaning(db_session, user_word):
                return None  # Duplicate meaning, don't schedule

            # basic_sr_schedule has UNIQUE (user_word_id), so of two requests
            # scheduling the same word only one insert survives. The window is
            # wide here, not theoretical: the validation above makes LLM calls,
            # so seconds can pass between the find() that came back empty and
            # this insert.
            #
            # Losing has to stay survivable. Callers can have their own pending
            # work in the session (report_exercise_outcome used to add the
            # learner's Exercise before scheduling, and lost it this way), so a
            # rollback of the whole session could discard it and surface as a
            # FAIL. The savepoint undoes this insert and nothing else, leaving
            # the caller's work to be committed as usual.
            try:
                with db_session.begin_nested():
                    schedule = cls(user_word)
                    user_word.level = 1
                    db_session.add_all([schedule, user_word])
                db_session.commit()
            except sqlalchemy.exc.IntegrityError:
                # Whoever won the race created it; use theirs.
                schedule = super(FourLevelsPerWord, cls).find(user_word)

        return schedule
