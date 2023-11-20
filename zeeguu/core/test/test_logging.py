from unittest import TestCase

from zeeguu.logging import log


class LoggingTest(TestCase):
    def test_logging(self):
        log("tüst")
