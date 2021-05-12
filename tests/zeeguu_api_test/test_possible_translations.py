# coding=utf-8
#
from unittest import TestCase
from unittest.mock import patch

from zeeguu_api_test.mocks.mock_translator import MockTranslator
from zeeguu_core_test.testing_data import VERY_EASY_STORY_URL
from zeeguu_api_test.api_test_mixin import APITestMixin
from zeeguu_api.api.translator import minimize_context


class TestPossibleTranslations(APITestMixin, TestCase):
    @patch("zeeguu_api.api.translate_and_bookmark.get_all_translations")
    def test_get_possible_translations(self, mock_get_all_translations):
        CONTEXT = "das ist sehr schon"
        WORD = "schon"
        TITLE = "lala"
        FROM_LANG_CODE = "de"
        TO_LANG_CODE = "en"
        API_ENDPOINT = "/get_possible_translations/%s/%s" % (
            FROM_LANG_CODE,
            TO_LANG_CODE,
        )
        MIN_CONTEXT, QUERY = minimize_context(CONTEXT, FROM_LANG_CODE, WORD)
        mock_get_all_translations.return_value = MockTranslator(
            {"schon": ["nice"]}
        ).translate(QUERY)

        with patch("zeeguu_api.api.translate_and_bookmark.minimize_context") as (
            mock_minimize_context
        ):
            mock_minimize_context.return_value = (MIN_CONTEXT, QUERY)
            translations = self.json_from_api_post(
                API_ENDPOINT,
                dict(context=CONTEXT, url=VERY_EASY_STORY_URL, word=WORD, title=TITLE),
            )
            mock_minimize_context.assert_called_once_with(CONTEXT, FROM_LANG_CODE, WORD)

        data = {
            "from_lang_code": FROM_LANG_CODE,
            "to_lang_code": TO_LANG_CODE,
            "context": CONTEXT,
            "url": VERY_EASY_STORY_URL,
            "word": WORD,
            "title": TITLE,
            "query": QUERY,
        }
        mock_get_all_translations.assert_called_once_with(data)
        assert "nice" in str(translations)

    @patch("zeeguu_api.api.translate_and_bookmark.get_all_translations")
    def test_get_possible_translations2(self, mock_get_all_translations):
        CONTEXT = (
            "Da sich nicht eindeutig erkennen lässt, "
            "ob Emojis Männer oder eben doch womöglich "
            "glatzköpfig Frauen darstellen,"
        )
        WORD = "glatzköpfig"
        TITLE = "lala"
        FROM_LANG_CODE = "de"
        TO_LANG_CODE = "en"
        API_ENDPOINT = "/get_possible_translations/%s/%s" % (
            FROM_LANG_CODE,
            TO_LANG_CODE,
        )
        MIN_CONTEXT, QUERY = minimize_context(CONTEXT, FROM_LANG_CODE, WORD)
        mock_get_all_translations.return_value = MockTranslator(
            {"glatzköpfig": ["gifpökztalg"]}
        ).translate(QUERY)

        with patch("zeeguu_api.api.translate_and_bookmark.minimize_context") as (
            mock_minimize_context
        ):
            mock_minimize_context.return_value = (MIN_CONTEXT, QUERY)
            translations = self.json_from_api_post(
                API_ENDPOINT,
                dict(context=CONTEXT, url=VERY_EASY_STORY_URL, word=WORD, title=TITLE),
            )
            mock_minimize_context.assert_called_once_with(CONTEXT, FROM_LANG_CODE, WORD)

        data = {
            "from_lang_code": FROM_LANG_CODE,
            "to_lang_code": TO_LANG_CODE,
            "context": CONTEXT,
            "url": VERY_EASY_STORY_URL,
            "word": WORD,
            "title": TITLE,
            "query": QUERY,
        }
        mock_get_all_translations.assert_called_once_with(data)
        assert "gifpökztalg" in str(translations)
