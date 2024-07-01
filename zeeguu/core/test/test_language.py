from unittest import TestCase

import zeeguu.core
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model.language import Language

db_session = zeeguu.core.model.db.session


class LanguageTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def test_languages_exists(self):
        language_should_be = LanguageRule().random

        try:
            language_to_check = Language.find(language_should_be.code)
        except NoResultFound:
            assert False, "No Language found in database"

        assert (
            language_should_be.code == language_to_check.code
            and language_should_be.name == language_to_check.name
        )

    def test_get_all_languages(self):
        languages = LanguageRule.languages

        for lan in languages:
            assert LanguageRule.get_or_create_language(lan)

    def test_user_set_language(self):
        from zeeguu.core.model import UserLanguage

        language_should_be = LanguageRule().random
        language_level_should_be = 2
        self.user.set_learned_language(
            language_should_be.code, language_level_should_be, db_session
        )
        db_session.commit()
        user_language = UserLanguage.find_or_create(
            db_session, self.user, language_should_be
        )
        assert (
            self.user.learned_language.id == language_should_be.id
            and user_language.cefr_level == language_level_should_be
        )

    def test_native_language(self):
        language_should_be = LanguageRule().random

        self.user.set_native_language(language_should_be.code)
        assert self.user.native_language.id == language_should_be.id
