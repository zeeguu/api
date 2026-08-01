"""The recipient decides the delivery language — never the sender.

Source language if the recipient learns it (→ simplify in it); otherwise their
primary learned language (→ translate + adapt). See
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


class _Upload:
    """Minimal stand-in — compute_delivery_language only reads .language."""

    def __init__(self, language):
        self.language = language


def _language_other_than(*language_ids):
    lang = LanguageRule().random
    while lang.id in language_ids:
        lang = LanguageRule().random
    return lang


class SharedArticleDeliveryLanguageTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.recipient = UserRule().user

    def test_source_language_when_recipient_learns_it(self):
        # A second language the recipient learns (not their primary).
        lang2 = _language_other_than(self.recipient.learned_language_id)
        UserLanguage.find_or_create(session, self.recipient, lang2)

        delivery, level = SharedArticle.compute_delivery_language(
            self.recipient, _Upload(lang2)
        )
        # Delivered in the article's own language, since the recipient learns it.
        assert delivery.id == lang2.id
        assert level in ("A1", "A2", "B1", "B2", "C1", "C2")

    def test_falls_back_to_primary_when_source_not_learned(self):
        foreign = _language_other_than(self.recipient.learned_language_id)

        delivery, _ = SharedArticle.compute_delivery_language(
            self.recipient, _Upload(foreign)
        )
        # Recipient doesn't learn the source language → their primary.
        assert delivery.id == self.recipient.learned_language_id
