# -*- coding: utf8 -*-
import logging
import sys


logger = logging.getLogger(__name__)
print(f"zeeguu_core initialized logger with name: {logger.name}")

logging.basicConfig(
    stream=sys.stdout, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


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


import zeeguu_core.word_scheduling.arts
import zeeguu_core.word_scheduling
import zeeguu_core.model.learner_stats.learner_stats
import zeeguu_core.model.learner_stats
import zeeguu_core.bookmark_quality
import zeeguu_core.content_recommender
import zeeguu_core.emailer
