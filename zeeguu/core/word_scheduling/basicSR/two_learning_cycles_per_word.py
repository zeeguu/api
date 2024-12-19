from .basicSR import ONE_DAY, BasicSRSchedule
from zeeguu.core.model import UserPreference
from datetime import datetime, timedelta
from zeeguu.core.model.learning_cycle import LearningCycle


# Implements either a single or a two-learning cycle schedule
# depending on whether the user has the productive exercises enabled
class TwoLearningCyclesPerWord(BasicSRSchedule):
    MAX_INTERVAL = 8 * ONE_DAY

    NEXT_COOLING_INTERVAL_ON_SUCCESS = {
        0: ONE_DAY,
        ONE_DAY: 2 * ONE_DAY,
        2 * ONE_DAY: 4 * ONE_DAY,
        4 * ONE_DAY: 8 * ONE_DAY,
    }

    # Reverse the process
    DECREASE_COOLING_INTERVAL_ON_FAIL = {
        v: k for k, v in NEXT_COOLING_INTERVAL_ON_SUCCESS.items()
    }
    # If at 0, we don't decrease it further.
    DECREASE_COOLING_INTERVAL_ON_FAIL[0] = 0

    def __init__(self, bookmark=None, bookmark_id=None):
        super(TwoLearningCyclesPerWord, self).__init__(bookmark, bookmark_id)

    def is_last_cycle(self):
        learning_cycle = self.bookmark.learning_cycle
        productive_exercises_enabled = (
            UserPreference.is_productive_exercises_preference_enabled(
                self.bookmark.user
            )
        )
        return not (
            learning_cycle == LearningCycle.RECEPTIVE and productive_exercises_enabled
        )

    def is_last_exercise_in_cycle(self):
        return self.cooling_interval == self.MAX_INTERVAL

    def is_about_to_be_learned(self):
        return self.is_last_cycle() and self.is_last_exercise_in_cycle()

    def update_schedule(self, db_session, correctness, exercise_time: datetime = None):

        if not exercise_time:
            exercise_time = datetime.now()

        new_cooling_interval = None

        if correctness:
            self.consecutive_correct_answers += 1
            if self.is_last_exercise_in_cycle():
                if self.is_last_cycle():
                    self.set_bookmark_as_learned(db_session)
                    return
                else:
                    # Switch learning_cycle to productive knowledge and reset cooling interval
                    self.bookmark.learning_cycle = LearningCycle.PRODUCTIVE
                    new_cooling_interval = 0
                    db_session.add(self.bookmark)

            else:
                # Since we can now lose the streak on day 8,
                # we might have to repeat it a few times to learn it.
                new_cooling_interval = self.NEXT_COOLING_INTERVAL_ON_SUCCESS.get(
                    self.cooling_interval, self.MAX_INTERVAL
                )
        else:
            # Decrease the cooling interval to the previous bucket
            new_cooling_interval = self.DECREASE_COOLING_INTERVAL_ON_FAIL[
                self.cooling_interval
            ]
            # Should we allow the user to "recover" their schedule
            # in the same day?
            # next_practice_date = exercise_time
            self.consecutive_correct_answers = 0

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
    def get_learning_cycle_length(cls):
        return len(cls.NEXT_COOLING_INTERVAL_ON_SUCCESS)

    @classmethod
    def find_or_create(cls, db_session, bookmark):

        schedule = super(TwoLearningCyclesPerWord, cls).find(bookmark)

        if not schedule:
            schedule = cls(bookmark)
            bookmark.learning_cycle = LearningCycle.RECEPTIVE
            db_session.add_all([schedule, bookmark])
            db_session.commit()

        return schedule
