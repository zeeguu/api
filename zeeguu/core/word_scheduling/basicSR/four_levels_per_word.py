from .basicSR import ONE_DAY, BasicSRSchedule
from datetime import datetime, timedelta

MAX_LEVEL = 4


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

    def __init__(self, user_meaning=None, user_meaning_id=None):
        super(FourLevelsPerWord, self).__init__(user_meaning, user_meaning_id)

    def is_about_to_be_learned(self):
        level_before_this_exercises = self.user_meaning.level
        return (
            self.cooling_interval == self.MAX_INTERVAL
            and level_before_this_exercises == MAX_LEVEL
        )

    def update_schedule(self, db_session, correctness, exercise_time: datetime = None):

        if not exercise_time:
            exercise_time = datetime.now()

        level_before_this_exercises = self.user_meaning.level

        if correctness:
            # Update level for user_meaning or mark as learned
            self.consecutive_correct_answers += 1
            if self.cooling_interval == self.MAX_INTERVAL:
                if level_before_this_exercises < MAX_LEVEL:
                    self.user_meaning.level = level_before_this_exercises + 1
                    db_session.add(self.user_meaning)

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

        # update next practice time for
        self.cooling_interval = new_cooling_interval
        next_practice_date = exercise_time + timedelta(minutes=new_cooling_interval)
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
    def find_or_create(cls, db_session, user_meaning):

        schedule = super(FourLevelsPerWord, cls).find(user_meaning)

        if not schedule:
            schedule = cls(user_meaning)
            user_meaning.level = 1
            db_session.add_all([schedule, user_meaning])
            db_session.commit()

        return schedule
