"""

Word scheduling algos

"""

from .basicSR.basicSR import BasicSRSchedule
from .basicSR.four_levels_per_word import FourLevelsPerWord, MINIMUM_COOLING_INTERVAL

from .basicSR.basicSR import ONE_DAY


def get_scheduler(user):

    return FourLevelsPerWord
