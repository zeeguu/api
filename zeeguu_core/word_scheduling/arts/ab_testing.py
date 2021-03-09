import configparser

from zeeguu_core.word_scheduling.arts.arts_rt import ArtsRT
from zeeguu_core.word_scheduling.arts.experiments.arts_diff_slow import ArtsDiffSlow
from zeeguu_core.word_scheduling.arts.algorithm_wrapper import AlgorithmWrapper


class ABTesting:

    _algorithms = [
            ArtsRT(),
            ArtsRT(0.1, 2, 1.1, 2, 20),
            ArtsDiffSlow()
            ]

    @classmethod
    def get_algorithm_for_id(cls, id):
        """Returns an algorithm from the_algorithms based on the modulo
        of the ID of the object and the number of algorithms

        :param id: An Integer, for which the algorithm should be returned
        :return: An AlgorithmWrapper containing an ArtsRT object with the parameters
                 specified in WORD_SCHEDULING_ALGORITHM_CONFIG
        """
        idx = cls.__get_algorithm_index_for_id(id)
        return cls._algorithms[idx]

    @classmethod
    def get_algorithm_wrapper_for_id(cls, id):
        algorithm = cls.get_algorithm_for_id(id)
        return AlgorithmWrapper(algorithm)

    @classmethod
    def split_bookmarks_based_on_algorithm(cls, bookmarks):
        groups = []
        for i in range(0, len(cls._algorithms)):
            groups.append([])

        for i in range(0, len(bookmarks)):
            group_idx = cls.__get_algorithm_index_for_id(bookmarks[i].id)
            groups[group_idx].append(bookmarks[i])

        return groups

    @classmethod
    def __get_algorithm_index_for_id(cls, id):
        count_algorithms = len(cls._algorithms)
        return divmod(id, count_algorithms)[1]
