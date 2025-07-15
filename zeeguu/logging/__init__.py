# -*- coding: utf8 -*-
import logging
from sentry_sdk import capture_exception
import sys


logger = logging.getLogger(__name__)
print(f"zeeguu.core initialized logger with name: {logger.name}")

logging.basicConfig(
    stream=sys.stdout, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


def info(msg):
    logger.info(msg)


def debug(msg):
    logger.debug(msg)


def log(msg):
    info(msg)
    print(msg)


def warning(msg):
    logger.warning(msg)


def critical(msg):
    logger.critical(msg)


def logp(msg):
    log(msg)
    print(msg)


def print_and_log_to_sentry(e: Exception):
    print(f"#### Exception: '{e}'")
    capture_exception(e)
