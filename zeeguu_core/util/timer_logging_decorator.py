import time

import zeeguu_core


def time_this(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        fname = func.__name__

        elapsed_time = (time.time() - start) * 1000
        zeeguu_core.info(fname + ' ran for ' + "{0:.2f}".format(elapsed_time) + 'ms')
        return result

    return wrapper
