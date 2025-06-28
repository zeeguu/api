import random

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.meaning_rule import MeaningRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.exercise_source_rule import ExerciseSourceRule
from zeeguu.core.model.exercise import Exercise
from datetime import datetime

from zeeguu.core.test.rules.user_word_rule import UserWordRule


class ExerciseRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.Exercise model class.

    Creates a Exercise object with random data and saves it to the database.
    """

    def __init__(
        self, exercise_session, outcome: OutcomeRule = None, date: datetime = None
    ):
        super().__init__()

        self.exercise = self._create_model_object(exercise_session, outcome, date)

        self.save(self.exercise)

    def _create_model_object(
        self, exercise_session, outcome: OutcomeRule = None, date: datetime = None
    ):

        random_outcome = outcome if outcome else OutcomeRule().random
        random_source = ExerciseSourceRule().random
        random_speed = random.randint(500, 5000)
        random_time = date if date else self.faker.date_time_this_year()
        random_meaning = MeaningRule().meaning
        user_word = UserWordRule(
            exercise_session.user, random_meaning
        ).user_word

        new_exercise = Exercise(
            random_outcome,
            random_source,
            random_speed,
            random_time,
            exercise_session.id,
            user_word,
        )

        if self._exists_in_db(new_exercise):
            return self._create_model_object()

        return new_exercise

    @staticmethod
    def _exists_in_db(obj):
        """Checks whether an object exists in the database already

        In this case, it will always return False since no unique constraint
        except for the row ID can be violated.

        :param obj: An Exercise, whose existence in the database needs to be checked
        :return: Always False
        """
        return False
