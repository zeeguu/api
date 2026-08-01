"""The recipient's copy is delivered in their PRIMARY/active learned language —
never routed into a merely-also-studied secondary. See
docs/future-work/article-body-provenance-and-sharing.md.
"""
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.language_rule import LanguageRule

import zeeguu.core
from zeeguu.core.model.shared_article import SharedArticle
from zeeguu.core.model.user_language import UserLanguage

session = zeeguu.core.model.db.session


class SharedArticleDeliveryLanguageTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.recipient = UserRule().user

    def _language_other_than(self, language_id):
        lang = LanguageRule().random
        while lang.id == language_id:
            lang = LanguageRule().random
        return lang

    def test_delivers_in_primary_language(self):
        delivery, level = SharedArticle.compute_delivery_language(self.recipient)
        assert delivery.id == self.recipient.learned_language_id
        assert level in ("A1", "A2", "B1", "B2", "C1", "C2")

    def test_does_not_route_into_a_studied_secondary_language(self):
        # The recipient also studies a second language — a share must still be
        # delivered in their primary, not hijacked into the secondary.
        secondary = self._language_other_than(self.recipient.learned_language_id)
        UserLanguage.find_or_create(session, self.recipient, secondary)

        delivery, _ = SharedArticle.compute_delivery_language(self.recipient)
        assert delivery.id == self.recipient.learned_language_id
        assert delivery.id != secondary.id
