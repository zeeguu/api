"""article_info surfaces the origin's CEFR level as parent_cefr_level for an
upload-sourced simplification, not only for one with a crawled parent article.

The reader's byline reads "Simplified to A1 from B2"; without this the level is
simply absent for anything shared into Zeeguu (extension or phone share), which
is how the byline silently lost its "from" half for those articles.
"""
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.url_rule import UrlRule

import zeeguu.core
from zeeguu.core.model.article_upload import ArticleUpload

session = zeeguu.core.model.db.session


class ArticleInfoOriginLevelTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.article = ArticleRule().article

    def _upload_of(self, origin_article):
        """An upload whose canonical article at that URL is `origin_article`."""
        upload = ArticleUpload(
            user=self.user, url=UrlRule().url, language=self.article.language,
            title="t", text_content="body",
        )
        upload.article_id = origin_article.id if origin_article else None
        session.add(upload)
        session.commit()
        return upload

    def test_origin_level_surfaces_for_upload_sourced_simplification(self):
        origin = ArticleRule().article
        origin.cefr_level = "B2"
        session.add(origin)
        session.commit()

        self.article.source_upload_id = self._upload_of(origin).id
        session.add(self.article)
        session.commit()

        info = self.article.article_info(with_content=False)
        assert info.get("parent_cefr_level") == "B2"

    def test_no_level_when_the_origin_has_none(self):
        origin = ArticleRule().article
        origin.cefr_level = None
        session.add(origin)
        session.commit()

        self.article.source_upload_id = self._upload_of(origin).id
        session.add(self.article)
        session.commit()

        info = self.article.article_info(with_content=False)
        assert "parent_cefr_level" not in info

    def test_no_level_when_the_upload_has_no_canonical_article_yet(self):
        self.article.source_upload_id = self._upload_of(None).id
        session.add(self.article)
        session.commit()

        info = self.article.article_info(with_content=False)
        assert "parent_cefr_level" not in info
