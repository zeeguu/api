import random


from zeeguu.core.bookmark_quality import bad_quality_bookmark
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.exercise_source_rule import ExerciseSourceRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.text_rule import TextRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling import (
    BasicSRSchedule,
)


class BookmarkTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user_rule = UserRule()
        self.user_rule.add_bookmarks(random.randint(3, 5))
        self.user = self.user_rule.user

    def test_user_has_bookmarks(self):
        assert self.user.has_bookmarks()

    def _helper_create_exercise(self, random_bookmark):

        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        random_exercise = ExerciseRule(exercise_session).exercise
        random_bookmark.add_new_exercise(random_exercise)

    def test_add_new_exercise(self):
        random_bookmark = BookmarkRule(self.user).bookmark

        length_original_exercise_log = len(random_bookmark.exercise_log)
        self._helper_create_exercise(random_bookmark)

        length_new_exercise_log = len(random_bookmark.exercise_log)
        assert length_original_exercise_log < length_new_exercise_log

    def test_bookmarks_to_study_is_not_empty(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        self._helper_create_exercise(random_bookmark)

        bookmarks = BasicSRSchedule.scheduled_bookmarks_due_today(self.user)

        assert bookmarks is not None

    def test_translation(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        assert random_bookmark.meaning.translation is not None

    def test_bookmarks_in_article(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        article = random_bookmark.text.article
        # each bookmark belongs to a random text / article so the
        # combo of user/article will always result in one bookmark
        assert 1 == len(Bookmark.find_all_for_user_and_article(self.user, article))

    def test_text_is_not_too_long(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        random_text_short = TextRule(length=10).text
        random_bookmark.text = random_text_short

        assert random_bookmark.content_is_not_too_long()

    def test_add_exercise_outcome(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        random_exercise = ExerciseRule(exercise_session).exercise
        random_bookmark.add_new_exercise_result(
            random_exercise.source,
            random_exercise.outcome,
            random_exercise.solving_speed,
            exercise_session.id,
        )
        latest_exercise = random_bookmark.exercise_log[-1]

        assert latest_exercise.source == random_exercise.source
        assert latest_exercise.outcome == random_exercise.outcome
        assert latest_exercise.solving_speed == random_exercise.solving_speed

    def test_user_bookmark_count(self):
        assert len(self.user.all_bookmarks()) > 0

    def test_bookmark_is_serializable(self):
        assert self.user.all_bookmarks()[0].as_dictionary()

    def test_bad_quality_bookmark(self):
        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 3)]

        random_bookmarks[0].meaning.origin = random_bookmarks[0].meaning.translation
        random_bookmarks[1].meaning.origin.content = self.faker.sentence(nb_words=10)
        random_bookmarks[2].meaning.origin.content = self.faker.word()[:2]

        for b in random_bookmarks:
            assert bad_quality_bookmark(b)

    def test_fit_for_study(self):
        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 2)]
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        random_exercise = ExerciseRule(exercise_session).exercise

        random_exercise.outcome = OutcomeRule().wrong

        random_bookmarks[0].starred = True
        random_bookmarks[1].starred = True
        random_bookmarks[1].add_new_exercise(random_exercise)

        for b in random_bookmarks:
            assert b.fit_for_study

    def test_add_new_exercise_result(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        exercise_count_before = len(random_bookmark.exercise_log)

        exercise_session = ExerciseSessionRule(self.user).exerciseSession

        random_bookmark.add_new_exercise_result(
            ExerciseSourceRule().random,
            OutcomeRule().random,
            random.randint(100, 1000),
            exercise_session.id,
        )

        exercise_count_after = len(random_bookmark.exercise_log)

        assert exercise_count_after > exercise_count_before

    def test_find_by_specific_user(self):
        list_should_be = self.user.all_bookmarks()
        list_to_check = Bookmark.find_by_specific_user(self.user)

        for b in list_should_be:
            assert b in list_to_check

    def test_find_all(self):
        list_should_be = self.user.all_bookmarks()
        list_to_check = Bookmark.find_all()

        for b in list_should_be:
            assert b in list_to_check

    def test_find_all_for_user_and_context(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find_all_for_context_and_user(
            bookmark_should_be.context, self.user
        )

        assert bookmark_should_be in bookmark_to_check

    def test_find(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find(bookmark_should_be.id)

        assert bookmark_to_check == bookmark_should_be

    def test_find_by_meaning_and_context(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find_by_meaning_and_context(
            self.user, bookmark_should_be.meaning, bookmark_should_be.context
        )

        assert bookmark_to_check == bookmark_should_be

    def test_exists(self):
        random_bookmark = self.user.all_bookmarks()[0]

        assert Bookmark.exists(random_bookmark)

    def test_latest_exercise_outcome(self):
        random_bookmark = self.user.all_bookmarks()[0]
        exercise_log = SortedExerciseLog(random_bookmark)
        assert exercise_log.latest_exercise_outcome() is None

        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        random_exercise = ExerciseRule(exercise_session).exercise

        random_bookmark.add_new_exercise(random_exercise)

        assert (
            random_exercise.outcome
            == SortedExerciseLog(random_bookmark).latest_exercise_outcome()
        )

    def test_empty_exercises_is_not_learned(self):
        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 4)]

        # Empty exercise_log should lead to a False return
        assert not any([bookmark.is_learned() for bookmark in random_bookmarks])
