import random

from zeeguu.core.model import UserExerciseSession
from zeeguu.core.test.rules.base_rule import BaseRule
from datetime import datetime


class ExerciseSessionRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.Exercise model class.

    Creates a Exercise object with random data and saves it to the database.
    """

    def __init__(self, user):
        super().__init__()

        self.exerciseSession = self._create_model_object(user)

        self.save(self.exerciseSession)

    def _create_model_object(self, user):
        new_session = UserExerciseSession(user.id, datetime.now())

        return new_session
