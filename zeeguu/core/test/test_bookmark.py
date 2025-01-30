import random

from zeeguu.core.bookmark_quality import top_bookmarks, bad_quality_bookmark
from zeeguu.core.definition_of_learned import is_learned_based_on_exercise_outcomes
from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog
from zeeguu.core.test.model_test_mixin import ModelTestMixIn

from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.exercise_session_rule import ExerciseSessionRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.source_rule import SourceRule
from zeeguu.core.test.rules.text_rule import TextRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model import Bookmark
from zeeguu.core.model import db
from zeeguu.core.word_scheduling import (
    TwoLearningCyclesPerWord,
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

        assert self.user.bookmarks_to_study(scheduled_only=True) is not None

    def test_translation(self):
        random_bookmark = BookmarkRule(self.user).bookmark
        assert random_bookmark.translation is not None

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
        assert self.user.all_bookmarks()[0].json_serializable_dict()

    def test_bad_quality_bookmark(self):
        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 3)]

        random_bookmarks[0].origin = random_bookmarks[0].translation
        random_bookmarks[1].origin.word = self.faker.sentence(nb_words=10)
        random_bookmarks[2].origin.word = self.faker.word()[:2]

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
            SourceRule().random,
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

    def find_all_for_user_and_text(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find_all_for_text_and_user(
            bookmark_should_be.text, self.user
        )

        assert bookmark_should_be in bookmark_to_check

    def test_find(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find(bookmark_should_be.id)

        assert bookmark_to_check == bookmark_should_be

    def test_find_all_by_user_and_word(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find_all_by_user_and_word(
            self.user, bookmark_should_be.origin
        )

        assert bookmark_should_be in bookmark_to_check

    def test_find_by_user_word_and_text(self):
        bookmark_should_be = self.user.all_bookmarks()[0]
        bookmark_to_check = Bookmark.find_by_user_word_and_text(
            self.user, bookmark_should_be.origin, bookmark_should_be.text
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
        learned = is_learned_based_on_exercise_outcomes(
            SortedExerciseLog(random_bookmarks[0])
        )
        assert not learned

    def test_is_too_easy_sets_to_learned(self):
        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 4)]

        # An exercise with Outcome equal to TOO EASY results in True, and time of last exercise
        exercise_session = ExerciseSessionRule(self.user).exerciseSession

        random_exercise = ExerciseRule(exercise_session).exercise

        random_exercise.outcome = OutcomeRule().too_easy
        random_bookmarks[1].add_new_exercise(random_exercise)
        learned = is_learned_based_on_exercise_outcomes(
            SortedExerciseLog(random_bookmarks[1])
        )
        result_time = SortedExerciseLog(random_bookmarks[1]).last_exercise_time()
        assert learned and result_time == random_exercise.time

        # Same test as above, but without a second return value
        learned = is_learned_based_on_exercise_outcomes(
            SortedExerciseLog(random_bookmarks[1])
        )
        assert learned

    def test_is_learned_based_on_exercise_outcomes_productive(self):
        from zeeguu.core.model.learning_cycle import LearningCycle
        from datetime import timedelta

        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 4)]
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        # A bookmark with CORRECTS_IN_A_ROW_FOR_LEARNED correct exercises in a row
        # returns true and the time of the last exercise
        total_exercises_productive_cycle = (
            TwoLearningCyclesPerWord.get_learning_cycle_length() * 2
        )
        correct_bookmark = random_bookmarks[2]
        correct_bookmark.learning_cycle = LearningCycle.PRODUCTIVE
        day_interval = 1
        distinct_dates = set()
        last_exercise_date = None
        while not (
            day_interval >= (total_exercises_productive_cycle)
            and len(distinct_dates) >= total_exercises_productive_cycle
        ):
            correct_exercise = ExerciseRule(exercise_session).exercise
            correct_exercise.outcome = OutcomeRule().correct
            correct_bookmark.add_new_exercise(correct_exercise)

            if not last_exercise_date:
                last_exercise_date = correct_exercise.time
            else:
                correct_exercise.time = last_exercise_date + timedelta(
                    days=day_interval
                )
                day_interval += 1
            last_exercise_date = correct_exercise.time
            distinct_dates.add(last_exercise_date.date())

        correct_bookmark.update_learned_status(db.session)
        db.session.commit()

        learned = correct_bookmark.is_learned_based_on_exercise_outcomes()
        assert learned

        log = SortedExerciseLog(correct_bookmark)
        learned_time_from_log = log.last_exercise_time()
        result_time = log.last_exercise_time()
        assert result_time == learned_time_from_log

        # A bookmark with no TOO EASY outcome or less than 5 correct exercises in a row
        # returns False, None
        wrong_exercise_bookmark = random_bookmarks[3]
        wrong_exercise = ExerciseRule(exercise_session).exercise
        wrong_exercise.outcome = OutcomeRule().wrong
        wrong_exercise_bookmark.add_new_exercise(wrong_exercise)

        learned = wrong_exercise_bookmark.is_learned_based_on_exercise_outcomes()
        assert not learned

    def test_is_learned_based_on_exercise_outcomes_receptive_not_set(self):

        random_bookmarks = [BookmarkRule(self.user).bookmark for _ in range(0, 4)]
        exercise_session = ExerciseSessionRule(self.user).exerciseSession
        # A bookmark with CORRECTS_IN_A_ROW_FOR_LEARNED correct exercises in a row
        # returns true and the time of the last exercise
        total_exercises_productive_cycle = (
            TwoLearningCyclesPerWord.get_learning_cycle_length()
        )
        correct_bookmark = random_bookmarks[2]
        exercises = 0
        distinct_dates = set()
        while not (
            exercises >= (total_exercises_productive_cycle)
            and len(distinct_dates) >= total_exercises_productive_cycle
        ):
            correct_exercise = ExerciseRule(exercise_session).exercise
            correct_exercise.outcome = OutcomeRule().correct
            correct_bookmark.add_new_exercise(correct_exercise)
            exercises += 1
            distinct_dates.add(correct_exercise.time.date())

        correct_bookmark.update_learned_status(db.session)

        learned = correct_bookmark.is_learned_based_on_exercise_outcomes()
        db.session.commit()

        assert learned

        log = SortedExerciseLog(correct_bookmark)
        learned_time_from_log = log.last_exercise_time()
        result_time = log.last_exercise_time()
        assert result_time == learned_time_from_log

        # A bookmark with no TOO EASY outcome or less than 5 correct exercises in a row returns False, None
        wrong_exercise_bookmark = random_bookmarks[3]
        wrong_exercise = ExerciseRule(exercise_session).exercise
        wrong_exercise.outcome = OutcomeRule().wrong
        random_bookmarks[3].add_new_exercise(wrong_exercise)

        learned = wrong_exercise_bookmark.is_learned_based_on_exercise_outcomes()
        assert not learned

    def test_top_bookmarks(self):
        assert top_bookmarks(self.user)
