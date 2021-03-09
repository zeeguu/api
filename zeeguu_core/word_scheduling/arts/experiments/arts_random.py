import random

from zeeguu_core.word_scheduling.arts.arts_base import ArtsBase


class ArtsRandom(ArtsBase):
    """A 'fake' implementation of the ARTS algorithm, which is used for AB-testing purposes.
    This class only returns a random priority so that we can test the effectiveness of the ARTS algorithm on learning
    performance against a random scheduler.
    """

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)

    def calculate(self, args):
        """Returns a random priority
        """
        return random.random()
