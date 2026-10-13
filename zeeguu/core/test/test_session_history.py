from datetime import datetime, timedelta

from sqlalchemy import event
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.exercise_source import ExerciseSource
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_source_rule import ExerciseSourceRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.user_statistics.exercise_corectness import (
    exercise_count_and_correctness_percentage,
)
from zeeguu.core.user_statistics.reading_sessions import summarize_reading_activity
from zeeguu.core.user_statistics.session_history import session_history

db_session = zeeguu.core.model.db.session

MINUTE_MS = 60 * 1000


class SessionHistoryTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.language = self.user.learned_language
        self.now = datetime.now()
        self.from_date = self.now - timedelta(days=60)
        self.to_date = self.now

    def _history(self, for_teacher=False, **kwargs):
        return session_history(
            self.user.id,
            self.language.id,
            kwargs.get("from_date", self.from_date),
            kwargs.get("to_date", self.to_date),
            for_teacher,
        )

    def _of_type(self, sessions, session_type):
        return [s for s in sessions if s["session_type"] == session_type]

    def _browsing(self, start, language=None):
        session = UserBrowsingSession(
            self.user.id, start, language_id=(language or self.language).id
        )
        session.duration = 2 * MINUTE_MS
        db_session.add(session)
        db_session.commit()
        return session

    def _reading(self, start, duration_ms=5 * MINUTE_MS):
        article = ArticleRule().article
        article.language = self.language
        session = UserReadingSession(self.user.id, article.id, start)
        session.duration = duration_ms
        session.last_action_time = start + timedelta(milliseconds=duration_ms)
        db_session.add(session)
        db_session.commit()
        return session

    def _exercise_session(self, start, outcomes):
        session = UserExerciseSession(self.user.id, start)
        session.duration = 3 * MINUTE_MS
        db_session.add(session)
        db_session.commit()
        source = ExerciseSourceRule().random
        for i, outcome in enumerate(outcomes):
            user_word = BookmarkRule(self.user).bookmark.user_word
            db_session.add(
                Exercise(
                    ExerciseOutcome.find_or_create(db_session, outcome),
                    source,
                    1000,
                    start + timedelta(seconds=i + 1),
                    session.id,
                    user_word,
                )
            )
        db_session.commit()
        return session

    def test_browsing_without_translations_is_shown(self):
        self._browsing(self.now - timedelta(days=1))

        browsing = self._of_type(self._history(), "browsing")

        assert len(browsing) == 1
        assert browsing[0]["words"] == []

    def test_browsing_in_another_language_is_not_shown(self):
        other = self.user.native_language
        self._browsing(self.now - timedelta(days=1), language=other)

        assert self._of_type(self._history(), "browsing") == []

    def test_to_date_is_honoured(self):
        self._browsing(self.now - timedelta(days=10))
        self._browsing(self.now - timedelta(days=2))

        sessions = self._history(to_date=self.now - timedelta(days=5))

        assert len(self._of_type(sessions, "browsing")) == 1

    def test_older_than_thirty_days(self):
        self._browsing(self.now - timedelta(days=45))

        assert len(self._of_type(self._history(), "browsing")) == 1

    def test_reading_session_has_article_length_and_difficulty(self):
        session = self._reading(self.now - timedelta(days=1))

        [reading] = self._of_type(self._history(), "reading")

        assert reading["article_word_count"] == session.article.word_count
        assert reading["article_difficulty"] == session.article.fk_difficulty

    def test_only_unaided_answers_count_as_correct(self):
        self._exercise_session(self.now - timedelta(days=1), ["C", "HC", "TC", "W"])

        [exercise] = self._of_type(self._history(), "exercise")

        assert exercise["correct_count"] == 1
        assert exercise["accuracy"] == 25
        assert [w["correct"] for w in exercise["words"]] == [True, False, False, False]

    def test_totals_match_the_teacher_dashboard(self):
        cohort = Cohort("hist-parity", "Parity", self.language, 10)
        db_session.add(cohort)
        db_session.commit()
        self._reading(self.now - timedelta(days=3), duration_ms=4 * MINUTE_MS)
        self._reading(self.now - timedelta(days=2), duration_ms=6 * MINUTE_MS)
        self._exercise_session(self.now - timedelta(days=2), ["C", "W", "C"])
        self._exercise_session(self.now - timedelta(days=1), ["HC", "C"])

        sessions = self._history()
        reading = self._of_type(sessions, "reading")
        exercises = self._of_type(sessions, "exercise")

        start, end = self.from_date.isoformat(), self.to_date.isoformat()
        dashboard_reading = summarize_reading_activity(
            self.user.id, cohort.id, start, end
        )
        dashboard_exercises = exercise_count_and_correctness_percentage(
            self.user.id, cohort.id, start, end
        )

        assert sum(s["duration"] for s in reading) // 1000 == (
            dashboard_reading["reading_time"]
        )
        total = sum(s["word_count"] for s in exercises)
        correct = sum(s["correct_count"] for s in exercises)
        assert total == dashboard_exercises["number_of_exercises"]
        assert int(correct / total * 100) / 100 == (
            dashboard_exercises["correct_on_1st_try"]
        )

    def test_teacher_sees_full_context_and_practised_flag(self):
        session = self._reading(self.now - timedelta(days=1))
        practised = BookmarkRule(self.user).bookmark
        not_practised = BookmarkRule(self.user).bookmark
        for b in (practised, not_practised):
            b.reading_session_id = session.id
        db_session.add(
            Exercise(
                ExerciseOutcome.find_or_create(db_session, "C"),
                ExerciseSourceRule().random,
                1000,
                self.now,
                None,
                practised.user_word,
            )
        )
        db_session.commit()

        [learner_view] = self._of_type(self._history(), "reading")
        [teacher_view] = self._of_type(self._history(for_teacher=True), "reading")

        assert all("practised" not in w for w in learner_view["words"])
        by_id = {w["id"]: w for w in teacher_view["words"]}
        assert by_id[practised.id]["practised"] is True
        assert by_id[not_practised.id]["practised"] is False
        assert by_id[practised.id]["context"] == practised.get_context()
        assert by_id[practised.id]["context_cut_right"] == bool(practised.context.right_ellipsis)

    def test_queries_do_not_grow_with_the_number_of_sessions(self):
        # The range is unbounded, so per-session lookups would make a school
        # year cost thousands of round trips.
        def add_day(days_ago):
            start = self.now - timedelta(days=days_ago)
            reading = self._reading(start)
            for _ in range(2):
                BookmarkRule(self.user).bookmark.reading_session_id = reading.id
            self._exercise_session(start - timedelta(hours=2), ["C", "W"])
            self._browsing(start - timedelta(hours=4))
            db_session.commit()

        def queries():
            db_session.expire_all()
            count = [0]

            def on_query(*_):
                count[0] += 1

            engine = db_session.get_bind()
            event.listen(engine, "before_cursor_execute", on_query)
            self._history(for_teacher=True)
            event.remove(engine, "before_cursor_execute", on_query)
            return count[0]

        add_day(1)
        with_one_day = queries()
        for days_ago in range(2, 6):
            add_day(days_ago)

        assert queries() == with_one_day

    def test_back_to_back_browsing_is_one_entry(self):
        day = self.now.replace(hour=12) - timedelta(days=1)
        self._browsing(day)
        self._browsing(day + timedelta(minutes=10))
        self._reading(day + timedelta(minutes=20))
        self._browsing(day + timedelta(minutes=40))
        self._browsing(day - timedelta(days=1))

        browsing = self._of_type(self._history(), "browsing")

        assert [b["merged_sessions"] for b in browsing] == [1, 2, 1]
        assert [b["duration"] for b in browsing] == [
            2 * MINUTE_MS,
            4 * MINUTE_MS,
            2 * MINUTE_MS,
        ]

    def test_browsing_hours_apart_stays_separate(self):
        # The 13 Oct case: two translations at 08:01, a quick browse at 17:30
        # with none. Merged, the second visit vanished into the morning one.
        day = self.now.replace(hour=8) - timedelta(days=1)
        self._browsing(day)
        self._browsing(day + timedelta(hours=9))

        browsing = self._of_type(self._history(), "browsing")

        assert [b["merged_sessions"] for b in browsing] == [1, 1]

    def test_audio_lesson_words_are_not_dashboard_exercises(self):
        # Session history never shows them (they belong to no exercise
        # session), so the dashboard must not count them either.
        cohort = Cohort("hist-audio", "Audio", self.language, 10)
        db_session.add(cohort)
        db_session.commit()
        self._exercise_session(self.now - timedelta(days=1), ["C", "W"])
        audio = ExerciseSource.find_or_create(db_session, "DAILY_AUDIO_LESSON")
        for outcome in ["C", ExerciseOutcome.LISTENED]:
            db_session.add(
                Exercise(
                    ExerciseOutcome.find_or_create(db_session, outcome),
                    audio,
                    0,
                    self.now - timedelta(hours=1),
                    None,
                    BookmarkRule(self.user).bookmark.user_word,
                )
            )
        db_session.commit()

        start, end = self.from_date.isoformat(), self.to_date.isoformat()
        stats = exercise_count_and_correctness_percentage(
            self.user.id, cohort.id, start, end
        )

        assert stats["number_of_exercises"] == 2
        assert stats["correct_on_1st_try"] == 0.5

    def test_times_are_marked_utc(self):
        # Stored naive in UTC; without the marker the browser reads them as
        # local time (2 h early in Copenhagen in summer).
        self._browsing(self.now - timedelta(days=1))

        [browsing] = self._of_type(self._history(), "browsing")

        assert browsing["start_time"].endswith("Z")
        assert browsing["end_time"].endswith("Z")
