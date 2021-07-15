from typing import Type

from zeeguu.core.language.difficulty_estimator_strategy import DifficultyEstimatorStrategy
from zeeguu.core.language.strategies.default_difficulty_estimator import DefaultDifficultyEstimator
from zeeguu.core.language.strategies.flesch_kincaid_difficulty_estimator import FleschKincaidDifficultyEstimator


class DifficultyEstimatorFactory:

    # Todo: Discover Difficulty Estimators
    _difficulty_estimators = {FleschKincaidDifficultyEstimator}
    _default_estimator = DefaultDifficultyEstimator

    @classmethod
    def get_difficulty_estimator(cls, estimator_name: str) -> Type[DifficultyEstimatorStrategy]:
        """
        Returns the difficulty estimator based on the given estimator name. It first checks if
        there are any estimators with the given class names. When nothing is found it checks the custom
        names of the class.
        :param estimator_name: String value name of the difficulty estimator class
        :return:
        """
        for estimator in cls._difficulty_estimators:
            if estimator.__name__ == estimator_name:
                return estimator

        for estimator in cls._difficulty_estimators:
            if estimator.has_custom_name(estimator_name):
                return estimator

        return cls._default_estimator
