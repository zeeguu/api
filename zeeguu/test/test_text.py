from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.text_rule import TextRule
from zeeguu.core.test.rules.user_rule import UserRule


class TextTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.text_rule = TextRule()
        self.user_rule = UserRule()
        self.bookmark_rule = BookmarkRule(self.user_rule.user)

    def test_user_word_count(self):
        self.assertIsNotNone(self.text_rule.text.content_hash)
