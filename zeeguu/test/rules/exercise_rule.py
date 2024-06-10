import random

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.source_rule import SourceRule
from zeeguu.core.model.exercise import Exercise


class ExerciseRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.Exercise model class.

    Creates a Exercise object with random data and saves it to the database.
    """

    def __init__(self, session):
        super().__init__()

        self.exercise = self._create_model_object(session.id)

        self.save(self.exercise)

    def _create_model_object(self, session_id):
        random_outcome = OutcomeRule().random
        random_source = SourceRule().random
        random_speed = random.randint(500, 5000)
        random_time = self.faker.date_time_this_year()

        new_exercise = Exercise(random_outcome, random_source, random_speed, random_time, session_id)

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
