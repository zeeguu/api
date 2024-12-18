from .basicSR import ONE_DAY, BasicSRSchedule
from datetime import datetime, timedelta

MAX_LEVEL = 4


# We are mapping cooling intervals to levels for users that migrate to LevelsSR, so their progress won't get lost.
COOLING_INTERVAL_TO_LEVEL_MAPPING = {
    0: 1,
    ONE_DAY: 1,
    2 * ONE_DAY: 2,
    4 * ONE_DAY: 3,
    8 * ONE_DAY: 4,
}

# Levels can be 1,2,3,4
# When an old bookmark is migrated to the Levels scheduler the level is set to 0
# When a new bookmark is created and the user has the LevelsSR it's level is automatically set to 1
#


class LevelsSR(BasicSRSchedule):

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

    def __init__(self, bookmark=None, bookmark_id=None):
        super(LevelsSR, self).__init__(bookmark, bookmark_id)

    def is_about_to_be_learned(self):
        level_before_this_exercises = self.bookmark.level
        return (
            self.cooling_interval == self.MAX_INTERVAL
            and level_before_this_exercises < MAX_LEVEL
        )

    def update_schedule(self, db_session, correctness):

        level_before_this_exercises = self.bookmark.level
        new_cooling_interval = None

        # handle bookmark that was migrated from the learning cycle scheduler
        # level can only be 0 if we did never encounter this bookmark in the context of levels SR
        if level_before_this_exercises == 0:
            newly_mapped_level = COOLING_INTERVAL_TO_LEVEL_MAPPING.get(
                self.cooling_interval, 1
            )
            self.bookmark.level = newly_mapped_level
            db_session.add(self.bookmark)

            # if we map on max level, we reset cooling so we give the learner the chance to
            # do one more time the final level before learning (and also because there's some
            # issue with the front-end)
            if newly_mapped_level == MAX_LEVEL:
                new_cooling_interval = 0

        if correctness:
            # Update level for bookmark or mark as learned
            self.consecutive_correct_answers += 1
            if self.cooling_interval == self.MAX_INTERVAL:
                if level_before_this_exercises < MAX_LEVEL:
                    self.bookmark.level = level_before_this_exercises + 1
                    db_session.add(self.bookmark)

                    # new exercise type can be done in the same day, thus cooling interval is 0
                    new_cooling_interval = 0

                else:
                    self.set_bookmark_as_learned(db_session)
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
        next_practice_date = datetime.now() + timedelta(minutes=new_cooling_interval)
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
    def get_learning_cycle_length(cls):
        return len(cls.NEXT_COOLING_INTERVAL_ON_SUCCESS)

    @classmethod
    def find_or_create(cls, db_session, bookmark):

        schedule = super(LevelsSR, cls).find(bookmark)

        if not schedule:
            schedule = cls(bookmark)
            bookmark.level = 1
            db_session.add_all([schedule, bookmark])
            db_session.commit()

        return schedule
