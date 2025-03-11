import math


def estimate_read_time(word_count: int, ceil: bool = True):
    """
    Returns the estimated reading time in minutes, assuming
    a reading rate of 160WPM.
    """
    return math.ceil(word_count / 160) if ceil else word_count / 160
