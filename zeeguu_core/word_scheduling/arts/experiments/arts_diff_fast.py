import math

from zeeguu_core.word_scheduling.arts.arts_base import ArtsBase


class ArtsDiffFast(ArtsBase):
    """
    ARTS algorithm with default values as described in:
    Adaptive response-time-based category sequencing in perceptual learning
    by Everett Mettler and Philip J. Kellma

    This class emphasizes the differences between (on average) fast reaction times more than between (on average)
    slow reaction times. This means that priorities of slightly different fast reaction times (e.g. 500ms and
    550ms) differ more significantly (e.g. 10 and 50) than the priorities of slightly different slow reaction times
    (e.g. 2000ms and 2050ms, with priorities of e.g. 10 and 12)

    a: Constant - general weight
    d: Constant - enforced delay (trials)
    b: Constant - weight for the response time
    r: Constant - weight for the standard deviation (inside log)
    w: Constant - priority increment for an error. Higher values let incorrect items appear quicker again
    """

    def __init__(self, a=0.1, d=2, b=1.1, r=1.7, w=20):
        self.a = a
        self.d = d
        self.b = b
        self.r = r
        self.w = w

    def calculate(self, N, alpha, sd):
        return self.a \
               * (N - self.d) \
               * (
                   (1 - alpha) * self.b * (math.e ** (self.r * sd))
                   + (alpha * self.w)
               )
