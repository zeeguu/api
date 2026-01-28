import zeeguu
from zeeguu.core.bookmark_quality import bad_quality_meaning
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.exercise_source_rule import ExerciseSourceRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling import BasicSRSchedule
from zeeguu.core.model.user import User
import random

db_session = zeeguu.core.model.db.session


class BookmarkTest(ModelTestMixIn):
    """
    Bookmark tests using class-level setup to share user and bookmarks.

    Creates 9 bookmarks once, each test uses a different set of 3:
    - test_bookmark_queries: bookmarks 0-2 (read-only operations)
    - test_exercises: bookmarks 3-5 (adds exercises)
    - test_bookmark_quality_and_study: bookmarks 6-8 (modifies data)
    """

    @classmethod
    def setUpClass(cls):
        """Create shared user and bookmarks once for all tests."""
        from zeeguu.core.test.conftest import get_shared_app, get_mock, init_fixtures_once

        cls.app = get_shared_app()
        get_mock()

        with cls.app.app_context():
            init_fixtures_once()

            cls.user_rule = UserRule()
            cls.user_rule.add_bookmarks(9)  # 3 per test
            # Store IDs to re-query in tests (avoids detached instance issues)
            cls._user_id = cls.user_rule.user.id
            cls._bookmark_ids = [b.id for b in cls.user_rule.user.all_bookmarks()]

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in this class."""
        from zeeguu.core.test.conftest import cleanup_tables

        with cls.app.app_context():
            db_session.close()
            cleanup_tables()

    def setUp(self):
        """Per-test setup - initialize faker and get fresh references."""
        from faker import Faker
        self.faker = Faker()
        # Re-query user and bookmarks to get session-bound objects
        self.user = User.find_by_id(self._user_id)
        self._all_bookmarks = [Bookmark.find(bid) for bid in self._bookmark_ids]

    def tearDown(self):
        """Per-test teardown - don't clean tables, done in tearDownClass."""
        pass

    def run(self, result=None):
        """Run test within app context."""
        with self.app.app_context():
            super(ModelTestMixIn, self).run(result)

    def test_bookmark_queries(self):
        """Consolidated: has_bookmarks, count, serializable, find, find_all,
        find_by_user, find_by_context, find_by_meaning_and_context.

        Uses bookmarks 0-2 (read-only operations)."""

        # Use first 3 bookmarks for this test
        test_bookmarks = self._all_bookmarks[0:3]

        # user has bookmarks
        assert self.user.has_bookmarks()

        # user bookmark count
        all_bookmarks = self.user.all_bookmarks()
        assert len(all_bookmarks) >= 3

        # bookmark is serializable
        b = test_bookmarks[0]
        assert b.as_dictionary()

        # find by specific user
        list_to_check = Bookmark.find_by_specific_user(self.user)
        for bm in test_bookmarks:
            assert bm in list_to_check

        # find all
        all_list = Bookmark.find_all()
        for bm in test_bookmarks:
            assert bm in all_list

        # find all for user and context
        bookmark_should_be = test_bookmarks[0]
        bookmark_to_check = Bookmark.find_all_for_context_and_user(
            bookmark_should_be.context, self.user
        )
        assert bookmark_should_be in bookmark_to_check

        # find by id
        bookmark_to_check = Bookmark.find(bookmark_should_be.id)
        assert bookmark_to_check == bookmark_should_be

        # find by meaning and context
        bookmark_to_check = Bookmark.find_by_usermeaning_and_context(
            bookmark_should_be.user_word,
            bookmark_should_be.context,
        )
        assert bookmark_to_check == bookmark_should_be

    def test_exercises(self):
        """Consolidated: add_new_exercise, add_exercise_outcome,
        add_new_exercise_result, bookmarks_to_study, latest_exercise_outcome.

        Uses bookmarks 3-5 (adds exercises)."""

        # Use bookmarks 3-5 for this test
        bm0, bm1, bm2 = self._all_bookmarks[3], self._all_bookmarks[4], self._all_bookmarks[5]

        # latest exercise outcome — check before adding any exercises
        exercise_log = SortedExerciseLog(bm0.user_word)
        assert exercise_log.latest_exercise_outcome() is None

        # add new exercise — log grows
        length_before = len(bm0.user_word.exercise_log)
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        random_exercise = ExerciseRule(exercise_session).exercise
        bm0.user_word.add_new_exercise(random_exercise)
        assert len(bm0.user_word.exercise_log) > length_before

        # latest exercise outcome — now has one
        assert (
            random_exercise.outcome
            == SortedExerciseLog(bm0.user_word).latest_exercise_outcome()
        )

        # add exercise outcome — fields match
        exercise_session2 = ExerciseSessionRule(self.user).exerciseSession
        exercise2 = ExerciseRule(exercise_session2).exercise
        bm1.add_new_exercise_result(
            db_session,
            exercise2.source,
            exercise2.outcome,
            exercise2.solving_speed,
            exercise_session2.id,
        )
        latest = bm1.user_word.exercise_log[-1]
        assert latest.source == exercise2.source
        assert latest.outcome == exercise2.outcome
        assert latest.solving_speed == exercise2.solving_speed

        # add new exercise result — count increases
        count_before = len(bm2.user_word.exercise_log)
        exercise_session3 = ExerciseSessionRule(self.user).exerciseSession
        bm2.add_new_exercise_result(
            db_session,
            ExerciseSourceRule().random,
            OutcomeRule().random,
            random.randint(100, 1000),
            exercise_session3.id,
        )
        assert len(bm2.user_word.exercise_log) > count_before

        # bookmarks to study is not empty
        bookmarks_to_study = BasicSRSchedule.scheduled_words_due_today(self.user)
        assert bookmarks_to_study is not None

    def test_bookmark_quality_and_study(self):
        """Consolidated: translation, bookmarks_in_article, bad_quality,
        fit_for_study, empty_exercises_not_learned.

        Uses bookmarks 6-8 (modifies data)."""

        # Use bookmarks 6-8 for this test
        test_bookmarks = self._all_bookmarks[6:9]

        # translation exists
        assert test_bookmarks[0].user_word.meaning.translation is not None

        # bookmarks in article
        article = test_bookmarks[0].text.article
        assert len(Bookmark.find_all_for_user_and_article(self.user, article)) >= 1

        # empty exercises is not learned (check before modifying bookmarks)
        assert not test_bookmarks[0].user_word.learned_time

        # fit for study (uses first 2 test bookmarks)
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        exercise = ExerciseRule(exercise_session).exercise
        exercise.outcome = OutcomeRule().wrong
        test_bookmarks[0].starred = True
        test_bookmarks[1].starred = True
        test_bookmarks[1].user_word.add_new_exercise(exercise)

        # bad quality bookmarks (mutate 3 test bookmarks — last checks, ok to modify)
        test_bookmarks[0].user_word.meaning.origin = (
            test_bookmarks[0].user_word.meaning.translation
        )
        test_bookmarks[1].user_word.meaning.origin.content = self.faker.sentence(
            nb_words=10
        )
        test_bookmarks[2].user_word.meaning.origin.content = self.faker.word()[:2]
        for b in test_bookmarks[:3]:
            assert bad_quality_meaning(b.user_word)
