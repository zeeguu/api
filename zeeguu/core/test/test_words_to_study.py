import random
from datetime import datetime

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.exercise_rule import ExerciseRule
from zeeguu.core.test.rules.outcome_rule import OutcomeRule
from zeeguu.core.test.rules.user_rule import UserRule


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
        # TODO

        # THEN
        # TODO

        # self.assertTrue(new_bookmark == bookmark,
                        # "The newly added bookmark has the highest priority")

