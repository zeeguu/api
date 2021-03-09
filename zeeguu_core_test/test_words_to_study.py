import random
from datetime import datetime

import zeeguu_core
from zeeguu_core_test.model_test_mixin import ModelTestMixIn
from zeeguu_core_test.rules.exercise_rule import ExerciseRule
from zeeguu_core_test.rules.outcome_rule import OutcomeRule
from zeeguu_core_test.rules.user_rule import UserRule
from zeeguu_core.word_scheduling.arts.ab_testing import ABTesting
from zeeguu_core.word_scheduling import arts


class WordsToStudyTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.BOOKMARK_COUNT = 20

        self.user_rule = UserRule()
        self.user_rule.add_bookmarks(self.BOOKMARK_COUNT, exercises_count=1)
        self.user = self.user_rule.user

    def test_new_bookmark_has_the_highest_priority(self):
        """ Adding a new bookmark, makes it the next thing to study """

        # GIVEN
        new_bookmark = self.user_rule.add_bookmarks(1)[0].bookmark

        # WHEN
        arts.update_bookmark_priority(zeeguu_core.db, self.user)

        # THEN
        bookmark = self.__get_bookmark_with_highest_priority()

        # print (bookmark)
        # print (new_bookmark)

        self.assertTrue(new_bookmark == bookmark,
                        "The newly added bookmark has the highest priority")

    def test_just_finished_bookmark_has_not_the_highest_priority(self):
        # GIVEN
        ABTesting._algorithms = [ABTesting._algorithms[random.randint(0, len(ABTesting._algorithms) - 1)]]
        arts.update_bookmark_priority(zeeguu_core.db, self.user)
        first_bookmark_to_study = self.__get_bookmark_with_highest_priority()

        # WHEN
        # Add an exercise
        exercise_rule = ExerciseRule()
        exercise_rule.exercise.time = datetime.now()
        exercise_rule.exercise.solving_speed = 100
        exercise_rule.exercise.outcome = OutcomeRule().correct
        first_bookmark_to_study.add_new_exercise(exercise_rule.exercise)

        arts.update_bookmark_priority(zeeguu_core.db, self.user)

        # THEN
        bookmark = self.__get_bookmark_with_highest_priority()
        assert first_bookmark_to_study != bookmark

    def __get_bookmark_with_highest_priority(self):
        bookmarks_to_study = self.user.bookmarks_to_study()
        if not bookmarks_to_study:
            return None
        return bookmarks_to_study[0]

    def __get_bookmark_with_lowest_priority(self):
        bookmarks_to_study = self.user.bookmarks_to_study()
        if len(bookmarks_to_study) == 0:
            return None

        return bookmarks_to_study[-1]
