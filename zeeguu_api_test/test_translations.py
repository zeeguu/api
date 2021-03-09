# coding=utf-8
from unittest import TestCase
from unittest.mock import patch, call

from zeeguu_api.api.translator import minimize_context
from zeeguu_api_test.api_test_mixin import APITestMixin
from zeeguu_api_test.mocks.mock_translator import MockTranslator
from zeeguu_core_test.test_data.mocking_the_web import url_spiegel_venezuela


class TranslationTests(APITestMixin, TestCase):
    def setUp(self):
        super(TranslationTests, self).setUp()
        FROM_LANG_CODE = "de"
        TO_LANG_CODE = "en"
        self.data = {
            "from_lang_code": FROM_LANG_CODE,
            "to_lang_code": TO_LANG_CODE,
            "context": None,
            "url": url_spiegel_venezuela,
            "word": None,
            "title": "",
            "query": None,
        }
        self.api_endpoint = "/get_possible_translations/%s/%s" % (
            FROM_LANG_CODE,
            TO_LANG_CODE,
        )

    @patch("zeeguu_api.api.translate_and_bookmark.get_all_translations")
    def test_get_possible_translations(self, mock_get_all_translations):
        self.data["context"] = "Die klein Jäger"
        self.data["word"] = "klein"
        MIN_CONTEXT, self.data["query"] = minimize_context(
            self.data["context"], self.data["from_lang_code"], self.data["word"]
        )
        mock_get_all_translations.return_value = MockTranslator(
            {"klein": ["small", "little"], "krassen": ["big"]}
        ).translate(self.data["query"])

        form_data = dict(
            url=self.data["url"], context=self.data["context"], word=self.data["word"]
        )
        with patch("zeeguu_api.api.translate_and_bookmark.minimize_context") as (
            mock_minimize_context
        ):
            mock_minimize_context.return_value = (MIN_CONTEXT, self.data["query"])
            alternatives = self.json_from_api_post(self.api_endpoint, form_data)
            mock_minimize_context.assert_called_once_with(
                self.data["context"], self.data["from_lang_code"], self.data["word"]
            )

        first_alternative = alternatives["translations"][0]
        second_alternative = alternatives["translations"][1]

        mock_get_all_translations.assert_called_once_with(self.data)
        assert first_alternative is not None
        assert second_alternative is not None
        assert first_alternative["likelihood"] >= second_alternative["likelihood"]

    @patch("zeeguu_api.api.translate_and_bookmark.get_all_translations")
    def test_get_translation_where_gslobe_fails_but_translate_succeeds(
        self, mock_get_all_translations
    ):
        self.data["context"] = "Die klein Jäger"
        self.data["word"] = "krassen"
        MIN_CONTEXT, self.data["query"] = minimize_context(
            self.data["context"], self.data["from_lang_code"], self.data["word"]
        )
        mock_get_all_translations.return_value = MockTranslator(
            {"klein": ["small"], "krassen": ["big", "extreme"]}
        ).translate(self.data["query"])

        form_data = dict(
            url=self.data["url"], context=self.data["context"], word=self.data["word"]
        )
        with patch("zeeguu_api.api.translate_and_bookmark.minimize_context") as (
            mock_minimize_context
        ):
            mock_minimize_context.return_value = (MIN_CONTEXT, self.data["query"])
            alternatives = self.json_from_api_post(self.api_endpoint, form_data)
            mock_minimize_context.assert_called_once_with(
                self.data["context"], self.data["from_lang_code"], self.data["word"]
            )

        mock_get_all_translations.assert_called_once_with(self.data)

        first_alternative = alternatives["translations"][0]
        assert first_alternative is not None

        second_alternative = alternatives["translations"][1]
        assert second_alternative is not None

    @patch("zeeguu_api.api.translate_and_bookmark.get_all_translations")
    def test_translate_and_bookmark(self, mock_get_all_translations):
        self.data["context"] = "Die klein Jäger"
        self.data["word"] = "Die"
        MIN_CONTEXT, self.data["query"] = minimize_context(
            self.data["context"], self.data["from_lang_code"], self.data["word"]
        )
        new_data = self.data.copy()
        new_data["word"] = "kleine"
        NEW_MIN_CONTEXT, new_data["query"] = minimize_context(
            new_data["context"], new_data["from_lang_code"], new_data["word"]
        )
        mock_translator = MockTranslator({"Die": ["The"], "kleine": ["small"]})
        new_mock_translator = MockTranslator({"Die": ["The"], "kleine": ["small"]})
        # bookmark1 call will modify the object, we need to return a copy of
        # the same object for bookmark2 call
        mock_get_all_translations.side_effect = [
            mock_translator.translate(self.data["query"]),
            mock_translator.translate(self.data["query"]),
            new_mock_translator.translate(new_data["query"]),
        ]

        form_data = dict(
            url=self.data["url"], context=self.data["context"], word=self.data["word"]
        )

        with patch("zeeguu_api.api.translate_and_bookmark.minimize_context") as (
            mock_minimize_context
        ):
            mock_minimize_context.return_value = (MIN_CONTEXT, self.data["query"])
            bookmark1 = self.json_from_api_post(
                "/translate_and_bookmark/%s/%s"
                % (self.data["from_lang_code"], self.data["to_lang_code"]),
                form_data,
            )
            bookmark2 = self.json_from_api_post(
                "/translate_and_bookmark/%s/%s"
                % (self.data["from_lang_code"], self.data["to_lang_code"]),
                form_data,
            )
            calls = [
                call(
                    self.data["context"], self.data["from_lang_code"], self.data["word"]
                )
            ] * 2
            mock_minimize_context.assert_has_calls(calls)

        assert bookmark1["bookmark_id"] == bookmark2["bookmark_id"]

        form_data["word"] = new_data["word"]
        with patch("zeeguu_api.api.translate_and_bookmark.minimize_context") as (
            mock_minimize_context
        ):
            mock_minimize_context.return_value = (NEW_MIN_CONTEXT, new_data["query"])
            bookmark3 = self.json_from_api_post(
                "/translate_and_bookmark/%s/%s"
                % (self.data["from_lang_code"], self.data["to_lang_code"]),
                form_data,
            )
            mock_minimize_context.assert_called_once_with(
                new_data["context"], new_data["from_lang_code"], new_data["word"]
            )

        calls = [call(self.data), call(self.data), call(new_data)]
        mock_get_all_translations.assert_has_calls(calls)
        self.assertTrue(bookmark3["translation"] == "small")

    def test_minimize_context(self):
        from zeeguu_api.api.translate_and_bookmark import minimize_context

        ctx = "Onderhandelaars ChristenUnie praten over positie homo-ouders"
        from_lang_code = "nl"
        word_str = "Onderhandelaars"

        assert minimize_context(ctx, from_lang_code, word_str)
