"""

Word scheduling algos

"""

from .basicSR.basicSR import BasicSRSchedule
from .basicSR.four_levels_per_word import FourLevelsPerWord

from .basicSR.basicSR import ONE_DAY


def get_scheduler(user):

    return FourLevelsPerWord
