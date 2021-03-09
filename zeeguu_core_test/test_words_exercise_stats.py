from zeeguu_core_test.model_test_mixin import ModelTestMixIn
from zeeguu_core_test.rules.user_rule import UserRule
from zeeguu_core.model.bookmark_priority_arts import BookmarkPriorityARTS
from zeeguu_core.word_scheduling import arts


class WordsExerciseStatsTest(ModelTestMixIn):

    def setUp(self):
        super().setUp()

        self.NUM_BOOKMARKS = 5

        self.user_rule = UserRule()
        self.user_rule.add_bookmarks(self.NUM_BOOKMARKS)
        self.user = self.user_rule.user
        self.NUM_BOOKMARKS = len(self.user.all_bookmarks_fit_for_study())

    def test_no_priority_without_run_of_algorithm(self):
        result = self.__get_table_count(BookmarkPriorityARTS)
        assert (result == 0)

    def test_update_bookmark_priority(self):
        # GIVEN

        # WHEN
        arts.update_bookmark_priority(self.db, self.user)

        # THEN
        result = self.__get_table_count(BookmarkPriorityARTS)
        assert (self.NUM_BOOKMARKS == result), (
            str(self.NUM_BOOKMARKS) + ' should be == to ' + str(result))

    def __get_table_count(self, cls):
        return self.db.session.query(cls).count()
