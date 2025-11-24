# -*- coding: utf8 -*-
import logging
from sentry_sdk import capture_exception
import sys


logger = logging.getLogger(__name__)

logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)


def log(msg):
    """Log to stdout at INFO level"""
    logger.info(msg)


def info(msg):
    logger.info(msg)


def debug(msg):
    logger.debug(msg)


def warning(msg):
    logger.warning(msg)


def critical(msg):
    logger.critical(msg)


def print_and_log_to_sentry(e: Exception):
    log(f"#### Exception: '{e}'")
    capture_exception(e)
