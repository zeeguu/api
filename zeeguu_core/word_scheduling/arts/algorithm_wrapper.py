from zeeguu_core.model.learner_stats.exercise_stats import ExerciseStats


class AlgorithmWrapper:
    """A Wrapper class for the ARTS algorithm implementations to calculate bookmark priorities.

    Needed to prepare the data received from the AlgorithmService for execution of the ARTS algorithm.
    This preparation is needed in order to use the ARTS algorithms without copy and pasting all
    preparation code (i.e. getting the N, alpha, and RT values) everywhere where the ARTS algorithm
    is to be used.
    """

    def __init__(self, algorithm):
        self.algorithm = algorithm

    def __eq__(self, other):
        return self.algorithm == other.algorithm

    def calculate(self, exercise, max_iterations):
        if exercise is None:
            raise ValueError("Exercise must not be None")

        args = self._args_prepare(exercise, max_iterations)
        return self.algorithm.calculate(args)

    def _args_prepare(self, exercise, max_iterations):
        """Gathers the parameters to later apply them when the algorithm.calculate method is being called
        INFO: This needs to be overwritten for other word scheduling algorithms according to their required calculate method

        :param exercise: The exercise (usually latest) to base the new priority on
        :param max_iterations: Current amount of total iterations/sessions of a user (ArtsRT parameter D)
        :return: parameters for algorithm.calculate
        """
        N = max_iterations - exercise.id
        alpha = not exercise.outcome.correct
        RT = exercise.solving_speed
        return N, alpha, RT


class AlgorithmSDCaller(AlgorithmWrapper):
    """A extension of the AlgorithmWrapper which calculates the Standard deviation of a reaction time from the
    population mean of an Exercise and passes it to the ARTS algorithm.

    This wrapper is needed for implementations of the ARTS algorithm which use the Standard Deviation instead of the
    Reaction Time (e.g. ArtsDiffSlow, ArtsDiffFast)
    """

    def _args_prepare(self, exercise, max_iterations):
        """ Overwritten original method of AlgorithmWrapper._args_prepare

        The standard deviation algorithms require the standard deviation in order to calculate the new priorities.

        """
        N = max_iterations - exercise.id
        alpha = not exercise.outcome.correct
        sd = self.convert_rt_to_sd(exercise)

        return N, alpha, sd

    def convert_rt_to_sd(self, exercise):
        exercise_stats = ExerciseStats.query.filter_by(exercise_source=exercise.source).one()
        return (exercise.solving_speed - exercise_stats.mean) / exercise_stats.sd
