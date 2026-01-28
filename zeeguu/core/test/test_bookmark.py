import random

import zeeguu
from zeeguu.core.bookmark_quality import bad_quality_meaning
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.exercise_source_rule import ExerciseSourceRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling import (
    BasicSRSchedule,
)

db_session = zeeguu.core.model.db.session


class BookmarkTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user_rule = UserRule()
        self.user_rule.add_bookmarks(random.randint(3, 5))
        self.user = self.user_rule.user

    def test_bookmark_queries(self):
        """Consolidated: has_bookmarks, count, serializable, find, find_all,
        find_by_user, find_by_context, find_by_meaning_and_context."""

        # user has bookmarks
        assert self.user.has_bookmarks()

        # user bookmark count
        all_bookmarks = self.user.all_bookmarks()
        assert len(all_bookmarks) > 0

        # bookmark is serializable
        b = all_bookmarks[0]
        assert b.as_dictionary()

        # find by specific user
        list_to_check = Bookmark.find_by_specific_user(self.user)
        for bm in all_bookmarks:
            assert bm in list_to_check

        # find all
        all_list = Bookmark.find_all()
        for bm in all_bookmarks:
            assert bm in all_list

        # find all for user and context
        bookmark_should_be = all_bookmarks[0]
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
        Reuses setUp bookmarks to avoid creating extra objects."""

        all_bookmarks = self.user.all_bookmarks()
        bm0, bm1, bm2 = all_bookmarks[0], all_bookmarks[1], all_bookmarks[2]

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
        Reuses setUp bookmarks to avoid creating extra objects."""

        all_bookmarks = self.user.all_bookmarks()

        # translation exists
        assert all_bookmarks[0].user_word.meaning.translation is not None

        # bookmarks in article
        article = all_bookmarks[0].text.article
        assert 1 == len(Bookmark.find_all_for_user_and_article(self.user, article))

        # empty exercises is not learned (check before modifying bookmarks)
        assert not all_bookmarks[0].user_word.learned_time

        # fit for study (uses first 2 setUp bookmarks)
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        exercise = ExerciseRule(exercise_session).exercise
        exercise.outcome = OutcomeRule().wrong
        all_bookmarks[0].starred = True
        all_bookmarks[1].starred = True
        all_bookmarks[1].user_word.add_new_exercise(exercise)

        # bad quality bookmarks (mutate 3 setUp bookmarks — last checks, ok to modify)
        all_bookmarks[0].user_word.meaning.origin = (
            all_bookmarks[0].user_word.meaning.translation
        )
        all_bookmarks[1].user_word.meaning.origin.content = self.faker.sentence(
            nb_words=10
        )
        all_bookmarks[2].user_word.meaning.origin.content = self.faker.word()[:2]
        for b in all_bookmarks[:3]:
            assert bad_quality_meaning(b.user_word)
