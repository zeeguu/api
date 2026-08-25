"""The inbox signature is what the client polls once a second instead of the
full inbox, so it has to move for every change the recipient would see rendered.
See SharedArticle.inbox_signature_for.
"""
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.article_rule import ArticleRule

import zeeguu.core
from zeeguu.core.model.shared_article import SharedArticle

session = zeeguu.core.model.db.session


class SharedArticleInboxSignatureTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.sender = UserRule().user
        self.recipient = UserRule().user
        self.article = ArticleRule().article

    def _signature(self):
        return SharedArticle.inbox_signature_for(self.recipient.id)

    def _share(self):
        return SharedArticle.create(
            session, self.sender.id, self.recipient.id, self.article.id
        )

    def test_stable_while_nothing_changes(self):
        self._share()
        assert self._signature() == self._signature()

    def test_moves_on_a_new_share(self):
        before = self._signature()
        self._share()
        assert self._signature() != before

    def test_moves_when_a_share_is_read(self):
        shared = self._share()
        before = self._signature()
        shared.mark_read(session)
        assert self._signature() != before

    def test_moves_when_a_share_is_dismissed(self):
        shared = self._share()
        before = self._signature()
        shared.dismiss(session)
        assert self._signature() != before

    def test_moves_when_the_delivery_derivative_lands(self):
        # The background-generated copy arriving is what flips a row from
        # "preparing" to openable — invisible to a plain count of the inbox.
        shared = self._share()
        before = self._signature()
        shared.delivery_article_id = ArticleRule().article.id
        session.add(shared)
        session.commit()
        assert self._signature() != before

    def test_ignores_shares_to_other_users(self):
        other = UserRule().user
        before = self._signature()
        SharedArticle.create(session, self.sender.id, other.id, self.article.id)
        assert self._signature() == before
