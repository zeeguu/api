from datetime import datetime, timedelta
from random import randint
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model.user_exercise_session import UserExerciseSession

class ExerciseSessionRule(BaseRule):
    """

        Creates a Exercise Session object with random data and saves it to the database.

    """
    def __init__(self):
        super().__init__()

        self.exercise_session = self._create_model_object()
        
        self.save(self.exercise_session)

    def _create_model_object(self):
        user_rule = UserRule()

        cohort = CohortRule()
        user = cohort.student1

        #UserRule and CohortRule give different user.id, therefore we equalize them so that all the information refers
        #to the same user
        user = user_rule.user

        start_time = datetime.now() - timedelta(minutes=randint(0, 7200))

        bookmark_rules = user_rule.add_bookmarks(bookmark_count=3, exercises_count=3)
        self.user = user_rule.user
        self.bookmark = bookmark_rules[0].bookmark

        exercise_session = UserExerciseSession(user.id, start_time)

        return exercise_session