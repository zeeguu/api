"""Resolving what a friend-share points at (the canonical article handle).

Core rule (docs/future-work/article-body-provenance-and-sharing.md): a share of
an upload-based copy resolves to the ONE canonical article at the publisher URL
— never a new synthetic row, and never by writing the upload's full body into a
recommendable article. The full body stays in the upload; only the handle is
resolved here.
"""
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

import zeeguu.core
from zeeguu.core.model.article import Article
from zeeguu.core.model.article_upload import ArticleUpload
from zeeguu.core.model.shared_article import SharedArticle

session = zeeguu.core.model.db.session


class SharedArticleResolutionTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        # A crawl stub sitting at a publisher URL — possibly a paywalled teaser.
        self.stub = ArticleRule().article
        self.publisher_url = self.stub.url.as_string()
        self.user = UserRule().user

    def _upload_at_stub_url(self, user, full_body="The COMPLETE article body."):
        return ArticleUpload.find_or_create(
            session,
            user=user,
            url_string=self.publisher_url,
            raw_html=None,
            text_content=full_body,
            title=self.stub.title,
            language_code=self.stub.language.code,
        )

    def test_upload_links_to_existing_crawl_at_creation(self):
        upload = self._upload_at_stub_url(self.user)
        # find_or_create links to the crawl already at the URL — no new article.
        assert upload.article_id == self.stub.id

    def test_share_of_upload_copy_resolves_to_canonical_stub(self):
        upload = self._upload_at_stub_url(self.user)

        # The sharer's copy: a derivative carrying source_upload_id (as the
        # send-and-simplify path produces today). We don't need a real
        # simplification here — only that it points at the upload.
        sharer_copy = ArticleRule().article
        sharer_copy.source_upload_id = upload.id
        session.add(sharer_copy)
        session.commit()

        resolved = SharedArticle.resolve_shareable_original_id(session, sharer_copy)

        # Resolves to the canonical stub — NOT the sharer's own copy, and NOT a
        # freshly minted synthetic row.
        assert resolved == self.stub.id
        assert resolved != sharer_copy.id

    def test_two_uploaders_same_url_share_one_canonical_article(self):
        other = UserRule().user
        upload_a = self._upload_at_stub_url(self.user, "Full body (subscriber).")
        upload_b = self._upload_at_stub_url(other, "Teaser only (no sub).")
        assert upload_a.id != upload_b.id
        # Many uploads : one article.
        assert upload_a.article_id == self.stub.id
        assert upload_b.article_id == self.stub.id

    def test_plain_crawl_resolves_to_itself(self):
        assert (
            SharedArticle.resolve_shareable_original_id(session, self.stub)
            == self.stub.id
        )

    def test_simplification_of_crawl_resolves_to_parent(self):
        child = ArticleRule().article
        child.parent_article_id = self.stub.id
        session.add(child)
        session.commit()
        assert (
            SharedArticle.resolve_shareable_original_id(session, child)
            == self.stub.id
        )
