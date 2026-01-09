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
            schedule = cls(user_word)
            user_word.level = 1
            db_session.add_all([schedule, user_word])
            db_session.commit()

        return schedule
