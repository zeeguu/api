import random

from wordstats.loading_from_hermit import load_language_from_hermit

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_word_rule import UserWordRule
from zeeguu.core.model import UserWord
from zeeguu.core.model import db


class UserWordTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

    def test_importance_level(self):
        random_word_stats = self.__get_random_word_stats()
        random_language = LanguageRule().get_or_create_language(
            random_word_stats[1].language_id
        )
        user_word = UserWord(random_word_stats[0], random_language)
        assert user_word.importance_level() == int(random_word_stats[1].importance)

    def test_find(self):
        user_word_should_be = UserWordRule().user_word
        user_word_to_check = UserWord.find(
            user_word_should_be.word, user_word_should_be.language
        )

        assert user_word_to_check == user_word_should_be

    def test_find_or_create(self):
        random_word = self.faker.word()
        random_language = LanguageRule().random
        user_word_not_in_db = UserWord(random_word, random_language)
        user_word_created = UserWord.find_or_create(
            db.session, random_word, random_language
        )

        assert user_word_created == user_word_not_in_db

    def test_find_all(self):
        list_random_user_words = [
            UserWordRule().user_word for _ in range(random.randint(2, 5))
        ]
        list_retrieved = UserWord.find_all()

        assert all([word in list_retrieved for word in list_random_user_words])

    def test_exists(self):
        user_word_in_db = UserWordRule().user_word
        assert UserWord.exists(user_word_in_db.word, user_word_in_db.language)

    def __get_random_word_stats(self):
        random_language = LanguageRule().random
        language_stats = load_language_from_hermit(random_language.code)
        return random.choice(list(language_stats.word_info_dict.items()))
