"""article_info exposes is_translated (cross-language) distinctly from
is_simplified (same-language level adaptation). Derived by comparing the
article's language to its origin's — see article-body-provenance-and-sharing.md.
"""
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.url_rule import UrlRule

import zeeguu.core
from zeeguu.core.model.article_upload import ArticleUpload

session = zeeguu.core.model.db.session


class ArticleInfoTranslatedFlagTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.article = ArticleRule().article

    def _upload_in(self, language):
        upload = ArticleUpload(
            user=self.user, url=UrlRule().url, language=language,
            title="t", text_content="body",
        )
        session.add(upload)
        session.commit()
        return upload

    def _other_language_than(self, language_id):
        lang = LanguageRule().random
        while lang.id == language_id:
            lang = LanguageRule().random
        return lang

    def test_is_translated_when_language_differs_from_origin(self):
        source_language = self.article.language
        target_language = self._other_language_than(source_language.id)
        upload = self._upload_in(source_language)

        self.article.source_upload_id = upload.id
        self.article.language = target_language  # "translated" into another language
        session.add(self.article)
        session.commit()

        info = self.article.article_info(with_content=False)
        assert info.get("is_translated") is True

    def test_not_translated_when_same_language_as_origin(self):
        upload = self._upload_in(self.article.language)
        self.article.source_upload_id = upload.id
        session.add(self.article)
        session.commit()

        info = self.article.article_info(with_content=False)
        assert not info.get("is_translated")
