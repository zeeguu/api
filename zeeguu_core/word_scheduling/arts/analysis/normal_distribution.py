import statistics


class NormalDistribution:
    """Calculates the normal distribution (mean and standard deviation) of a iterable of values
    """

    @staticmethod
    def calc_normal_distribution(values):
        mean = statistics.mean(values)
        sd = statistics.stdev(values)
        return mean, sd
