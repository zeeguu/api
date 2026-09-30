"""
CRAWL_SCHEDULE is the one place that lists crawled languages.

Bulgarian took three fixes to go live because the list was copied into the
crontab, the crawl shell script, and crawl.py, and each copy rejected bg in its
own way. These tests pin that everything now derives from the schedule, and
that the CLI the shell script parses keeps its shape.
"""

import subprocess
import sys
from unittest import TestCase

import zeeguu.core.crawl_schedule as crawl_schedule
from zeeguu.core.crawl_schedule import CRAWL_SCHEDULE, languages_due_at
from zeeguu.core.model.language import Language


class CrawlScheduleTest(TestCase):

    def test_language_codes_come_from_the_schedule(self):
        self.assertEqual(Language.CODES_OF_LANGUAGES_BEING_CRAWLED, list(CRAWL_SCHEDULE))

    def test_every_scheduled_language_has_a_name(self):
        for code in CRAWL_SCHEDULE:
            self.assertIn(code, Language.LANGUAGE_NAMES)

    def test_hours_are_real_hours(self):
        for code, crawl in CRAWL_SCHEDULE.items():
            for hour in crawl.hours:
                self.assertTrue(0 <= hour <= 23, f"{code}: {hour}")

    def test_bulgarian_is_crawled_three_times_a_day(self):
        for hour in (9, 14, 20):
            self.assertIn("bg", languages_due_at(hour))
        self.assertNotIn("bg", languages_due_at(11))

    def test_hourly_languages_go_first(self):
        # A slow 3x-a-day language must not delay the hourly ones.
        self.assertEqual(languages_due_at(9)[:3], ["da", "fr", "de"])
        self.assertEqual(languages_due_at(11), ["da", "fr", "de"])

    def test_paused_language_is_offered_but_never_due(self):
        self.assertIn("sv", Language.CODES_OF_LANGUAGES_BEING_CRAWLED)
        self.assertFalse(any("sv" in languages_due_at(h) for h in range(24)))


class CrawlScheduleCliTest(TestCase):
    """crawl_all_in_parallel.sh runs the file with plain python3 and reads its stdout."""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, crawl_schedule.__file__, *args],
            capture_output=True,
            text=True,
        )

    def test_prints_code_articles_minutes_per_due_language(self):
        result = self._run("--hour", "11")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["da 100 50", "fr 40 50", "de 20 25"])

    def test_explicit_languages_run_even_when_not_due(self):
        result = self._run("bg", "sv")
        self.assertEqual(result.stdout.splitlines(), ["bg 5 25", "sv 5 25"])

    def test_unknown_language_fails_loudly(self):
        result = self._run("xx")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("xx", result.stderr)
