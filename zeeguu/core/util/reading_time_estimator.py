import math


def estimate_read_time(word_count: int):
    """
    Returns the estimated reading time in minutes, assuming
    a reading rate of 160WPM.
    """
    return math.ceil(word_count / 160)
