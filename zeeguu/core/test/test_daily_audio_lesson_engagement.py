"""
Engagement-gate logic for daily audio lessons (PR #646).

is_engaged must measure the FURTHEST position reached (max_position_seconds),
not the resume pointer (pause_position_seconds) which drops on a rewind. These
are pure in-memory checks on the model — no persistence needed.
"""

from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule


class DailyAudioLessonEngagementTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        user = UserRule().user
        # 360s lesson; engagement threshold is 50% → 180s.
        self.lesson = DailyAudioLesson(
            user=user,
            created_by="test",
            duration_seconds=360,
            language=user.learned_language,
            lesson_type="topic",
        )

    def test_fresh_lesson_not_engaged(self):
        assert not self.lesson.is_engaged

    def test_below_half_not_engaged(self):
        self.lesson.pause_at(108)  # 30%
        assert self.lesson.max_position_seconds == 108
        assert not self.lesson.is_engaged

    def test_at_half_is_engaged(self):
        self.lesson.pause_at(180)  # exactly 50%
        assert self.lesson.is_engaged

    def test_rewind_keeps_engagement(self):
        # The bug this PR fixes: reach 80%, then scrub back and pause at 30s.
        self.lesson.pause_at(290)  # ~80% → engaged
        assert self.lesson.is_engaged
        self.lesson.pause_at(30)  # rewind: resume pointer drops…
        assert self.lesson.pause_position_seconds == 30  # …resume follows the playhead
        assert self.lesson.max_position_seconds == 290  # …but the high-water mark holds
        assert self.lesson.is_engaged  # still engaged — the bug would say False

    def test_pause_clamps_to_duration(self):
        self.lesson.pause_at(10_000)
        assert self.lesson.pause_position_seconds == 360
        assert self.lesson.max_position_seconds == 360

    def test_completed_is_engaged_and_credits_full_duration(self):
        self.lesson.mark_completed()
        assert self.lesson.is_engaged
        assert self.lesson.max_position_seconds == 360
        assert self.lesson.pause_position_seconds == 0  # resume reset on completion

    def test_legacy_row_falls_back_to_pause_position(self):
        # A row written before max_position_seconds existed (backfill would set
        # it, but simulate the in-memory fallback): only pause_position is set.
        self.lesson.max_position_seconds = 0
        self.lesson.pause_position_seconds = 200  # 55%
        assert self.lesson.is_engaged

    def test_no_duration_falls_back_to_started(self):
        self.lesson.duration_seconds = None
        assert not self.lesson.is_engaged
        self.lesson.pause_at(5)
        assert self.lesson.is_engaged
