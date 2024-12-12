from .basicSR import ONE_DAY, BasicSRSchedule
from zeeguu.core.model import db, ExerciseOutcome
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

    def update_schedule(self, db_session, correctness):

        level = self.bookmark.level

        first_time_scheduled_with_levels_sr = False
        if level == 0:
            level = COOLING_INTERVAL_TO_LEVEL_MAPPING.get(self.cooling_interval, 1)
            first_time_scheduled_with_levels_sr = True

        if correctness:

            # can be more than max if the bookmark was scheduled with the old scheduler
            if self.cooling_interval >= self.MAX_INTERVAL:

                # Update level for bookmark
                if level < MAX_LEVEL:
                    # Bookmark will move to the next level
                    self.bookmark.level = level + 1
                    db_session.add(self.bookmark)
                    self.cooling_interval = 0
                    return
                if level == MAX_LEVEL and first_time_scheduled_with_levels_sr:
                    self.cooling_interval = 0
                    db_session.add(self.bookmark)
                    self.cooling_interval = 0
                    return
                else:
                    self.set_bookmark_as_learned(db_session)
                    return

            # Not going to next level, but update cooling interval
            # =========================

            new_cooling_interval = self.NEXT_COOLING_INTERVAL_ON_SUCCESS.get(
                self.cooling_interval, self.MAX_INTERVAL
            )
            self.consecutive_correct_answers += 1
        else:
            # correctness = FALSE ==> bookmark was not correct
            # ==================================================

            # Decrease the cooling interval to the previous bucket
            new_cooling_interval = self.DECREASE_COOLING_INTERVAL_ON_FAIL[
                self.cooling_interval
            ]
            # Should we allow the user to "recover" their schedule
            # in the same day?
            # next_practice_date = datetime.now()
            # ML: TODO: I think we are not using consecutive_correct_answers and we should remove it
            self.consecutive_correct_answers = 0

        # correct, but no upgrade of level or incorrect
        self.bookmark.level = level  # set the level for migration to be finallized
        db_session.add(self.bookmark)

        # update next practice time for
        self.cooling_interval = new_cooling_interval
        next_practice_date = datetime.now() + timedelta(minutes=new_cooling_interval)
        self.next_practice_time = next_practice_date

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
    def update(cls, db_session, bookmark, outcome):

        if outcome == ExerciseOutcome.OTHER_FEEDBACK:
            from zeeguu.core.model.bookmark_user_preference import UserWordExPreference

            schedule = cls.find_or_create(db_session, bookmark)
            bookmark.fit_for_study = 0
            ## Since the user has explicitly given feedback, this should
            # be recorded as a user preference.
            bookmark.user_preference = UserWordExPreference.DONT_USE_IN_EXERCISES
            db_session.add(bookmark)
            db_session.delete(schedule)
            return

        correctness = ExerciseOutcome.is_correct(outcome)
        schedule = cls.find_or_create(db_session, bookmark)

        if schedule.there_was_no_need_for_practice_today():
            return
        schedule.update_schedule(db_session, correctness)
        # Duplication with learning_cycle_sr
        # Is this line not needed? How come? There are branches in update_schedule
        # that modify cooling interval and return w/o adding it to the session
        db_session.add(schedule)

    @classmethod
    def find_or_create(cls, db_session, bookmark):

        results = cls.query.filter_by(bookmark=bookmark).all()
        print(results)
        if len(results) == 1:
            print(len(results))
            print("getting the first element in results")
            return results[0]

        if len(results) > 1:
            raise Exception(
                f"More than one Bookmark schedule entry found for {bookmark.id}"
            )

        # create a new one
        schedule = cls(bookmark)
        bookmark.level = 1
        db_session.add_all([schedule, bookmark])
        db_session.commit()
        return schedule
