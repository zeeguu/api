#!/usr/bin/env python3
"""
The single place that says which languages we crawl, when, and how much.

Everything else derives from CRAWL_SCHEDULE:
  - Language.CODES_OF_LANGUAGES_BEING_CRAWLED (what the app offers, and what
    crawl.py accepts)
  - crawl_all_in_parallel.sh, which cron calls once an hour and which asks
    this module which languages are due and with what limits

Adding a language = one line here (plus its feeds in the DB).

This file is stdlib-only on purpose: crawl_all_in_parallel.sh runs it with the
host's python3, outside docker, so it reads the host clock -- the same one cron
uses.

CLI (used by crawl_all_in_parallel.sh; one "code max_articles max_minutes"
line per language, in crawl order):
    python3 crawl_schedule.py              # languages due this hour
    python3 crawl_schedule.py --hour 10    # languages due at 10:xx
    python3 crawl_schedule.py da fr        # just these, due or not
"""
import argparse
import sys
from datetime import datetime
from typing import NamedTuple

EVERY_HOUR = tuple(range(24))
# 9, not 10: the run starts at :37 with the hourly languages, so the 09:37 run
# finishes these around 10:15 -- before the 11:00 feed_delivery_health check that
# expects today's crawl to be in (see ops cron/zeeguu.crontab).
THREE_TIMES_A_DAY = (9, 14, 20)
# Still offered in the app (existing readers keep their articles), no new crawls.
PAUSED = ()

DEFAULT_MAX_MINUTES = 25
HIGH_VOLUME_MAX_MINUTES = 50  # more users + bigger backlogs


class LanguageCrawl(NamedTuple):
    hours: tuple
    max_articles: int
    max_minutes: int = DEFAULT_MAX_MINUTES


# Crawl order within a run is the order below. Hourly languages go first so a
# slow 3x-a-day language can't delay them.
CRAWL_SCHEDULE = {
    "da": LanguageCrawl(EVERY_HOUR, 100, HIGH_VOLUME_MAX_MINUTES),
    "fr": LanguageCrawl(EVERY_HOUR, 40, HIGH_VOLUME_MAX_MINUTES),
    "de": LanguageCrawl(EVERY_HOUR, 20),
    "pt": LanguageCrawl(THREE_TIMES_A_DAY, 5),
    "ro": LanguageCrawl(THREE_TIMES_A_DAY, 5),
    "nl": LanguageCrawl(THREE_TIMES_A_DAY, 15),
    "en": LanguageCrawl(THREE_TIMES_A_DAY, 20),
    "el": LanguageCrawl(THREE_TIMES_A_DAY, 5),
    "es": LanguageCrawl(THREE_TIMES_A_DAY, 5),
    "it": LanguageCrawl(THREE_TIMES_A_DAY, 5),
    "bg": LanguageCrawl(THREE_TIMES_A_DAY, 5),
    "sv": LanguageCrawl(PAUSED, 5),
}


def languages_due_at(hour):
    return [code for code, crawl in CRAWL_SCHEDULE.items() if hour in crawl.hours]


def _main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("languages", nargs="*", help="crawl these instead of the ones due now")
    parser.add_argument("--hour", type=int, default=None, help="pretend it's this hour (0-23)")
    args = parser.parse_args(argv)

    if args.languages:
        unknown = [code for code in args.languages if code not in CRAWL_SCHEDULE]
        if unknown:
            print(f"Not in CRAWL_SCHEDULE: {unknown}. Known: {list(CRAWL_SCHEDULE)}", file=sys.stderr)
            return 1
        codes = args.languages
    else:
        hour = datetime.now().hour if args.hour is None else args.hour
        codes = languages_due_at(hour)

    for code in codes:
        crawl = CRAWL_SCHEDULE[code]
        print(code, crawl.max_articles, crawl.max_minutes)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
