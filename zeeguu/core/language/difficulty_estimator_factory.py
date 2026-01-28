from typing import Type

from zeeguu.core.language.difficulty_estimator_strategy import DifficultyEstimatorStrategy


# Lazy-loaded estimators to avoid importing nltk/scipy at module load time
_difficulty_estimators = None
_default_estimator = None


def _get_estimators():
    """Lazily load estimator classes to defer heavy imports (nltk, scipy)."""
    global _difficulty_estimators, _default_estimator
    if _difficulty_estimators is None:
        from zeeguu.core.language.strategies.default_difficulty_estimator import DefaultDifficultyEstimator
        from zeeguu.core.language.strategies.flesch_kincaid_difficulty_estimator import FleschKincaidDifficultyEstimator
        _difficulty_estimators = {FleschKincaidDifficultyEstimator}
        _default_estimator = DefaultDifficultyEstimator
    return _difficulty_estimators, _default_estimator


class DifficultyEstimatorFactory:

    @classmethod
    def get_difficulty_estimator(cls, estimator_name: str) -> Type[DifficultyEstimatorStrategy]:
        """
        Returns the difficulty estimator based on the given estimator name. It first checks if
        there are any estimators with the given class names. When nothing is found it checks the custom
        names of the class.
        :param estimator_name: String value name of the difficulty estimator class
        :return:
        """
        estimators, default = _get_estimators()

        for estimator in estimators:
            if estimator.__name__ == estimator_name:
                return estimator

        for estimator in estimators:
            if estimator.has_custom_name(estimator_name):
                return estimator

        return default
