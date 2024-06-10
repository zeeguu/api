from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.user_word_rule import UserWordRule
from zeeguu.core.model.user_preference import UserPreference
from zeeguu.core.model import db


class UserPreferenceTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.user_rule = UserRule()
        self.user = self.user_rule.user
        db.session.add(self.user)
        db.session.commit()

        self.random_origin_word = self.faker.word()
        self.random_origin_language = LanguageRule().random
        self.user_word_rule = UserWordRule(
            self.random_origin_word, self.random_origin_language
        )

        self.text = "This sentence, taken as a reading passage unto itself, is being used to prove a point."
        self.english = LanguageRule().get_or_create_language("en")

    def test_no_preference_at_first(self):
        assert not UserPreference.get_difficulty_estimator(self.user)

    def test_setting_preference(self):

        UserPreference.set_difficulty_estimator(db.session, self.user, "fk")
        assert UserPreference.get_difficulty_estimator(self.user) == "fk"

    def test_text_difficulty_with_preference(self):

        # with the default estimator (Frequency) the difficulty is EASY
        difficulty = self.user.text_difficulty(self.text, self.english)
        assert difficulty["discrete"] == "MEDIUM"

        # setting a preference for this user
        p = UserPreference.set_difficulty_estimator(db.session, self.user, "frequency")

        # with fk difficulty for the example text is MEDIUM
        difficulty = self.user.text_difficulty(self.text, self.english)
        assert difficulty["discrete"] == "EASY"
