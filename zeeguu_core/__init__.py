# -*- coding: utf8 -*-
import logging

logger = logging.getLogger(__name__)
print(f"zeeguu_core initialized logger with name: {logger.name}")

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")


def info(msg):
    logger.info(msg)

def debug(msg):
    logger.debug(msg)


def log(msg):
    info(msg)


def warning(msg):
    logger.warning(msg)


def critical(msg):
    logger.critical(msg)


def logp(msg):
    log(msg)
    print(msg)
