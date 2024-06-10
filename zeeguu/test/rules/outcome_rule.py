import random

from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.model.exercise_outcome import ExerciseOutcome


class OutcomeRule(BaseRule):
    """A Testing Rule class for ExerciseOutcomes

    Has all supported outcomes as properties. Outcomes are created and
    saved to the database if they don't yet exist in the database.
    """

    outcomes = [
        ExerciseOutcome.CORRECT,
        ExerciseOutcome.TOO_EASY,
        ExerciseOutcome.WRONG,
        ExerciseOutcome.SHOW_SOLUTION,
        ExerciseOutcome.RETRY,
        ExerciseOutcome.TYPO
    ]

    @classmethod
    def __get_or_create_outcome(cls, outcome):
        try:
            return ExerciseOutcome.find(outcome)
        except NoResultFound:
            return cls.__create_new_outcome(outcome)

    @classmethod
    def __create_new_outcome(cls, outcome):
        new_outcome = ExerciseOutcome(outcome)

        cls.save(new_outcome)

        return new_outcome

    @property
    def show_solution(self):
        return self.__get_or_create_outcome(ExerciseOutcome.SHOW_SOLUTION)

    @property
    def retry(self):
        return self.__get_or_create_outcome(ExerciseOutcome.RETRY)

    @property
    def correct(self):
        return self.__get_or_create_outcome(ExerciseOutcome.CORRECT)

    @property
    def wrong(self):
        return self.__get_or_create_outcome(ExerciseOutcome.WRONG)

    @property
    def typo(self):
        return self.__get_or_create_outcome(ExerciseOutcome.TYPO)

    @property
    def too_easy(self):
        return self.__get_or_create_outcome(ExerciseOutcome.TOO_EASY)

    @property
    def random(self):
        random_outcome = random.choice(self.outcomes)
        return self.__get_or_create_outcome(random_outcome)
