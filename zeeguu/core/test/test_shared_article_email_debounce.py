"""Temporal debounce for the share-notification email: a burst to the same
recipient collapses to one email, but a genuinely later share still notifies.
See emailer/shared_article.py.
"""
from datetime import datetime, timedelta
from unittest import TestCase

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.test.rules.article_rule import ArticleRule

import zeeguu.core
from zeeguu.core.model.shared_article import SharedArticle

session = zeeguu.core.model.db.session


class SharedArticleEmailDebounceTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.sender = UserRule().user
        self.recipient = UserRule().user
        self.article = ArticleRule().article

    def _share_at(self, when, to_user=None):
        shared = SharedArticle.create(
            session, self.sender.id, (to_user or self.recipient).id, self.article.id
        )
        shared.created_at = when  # explicit, so the test doesn't depend on DB clock/tz
        session.add(shared)
        session.commit()
        return shared

    def test_first_of_a_burst_notifies_rest_suppressed(self):
        now = datetime.now()
        first = self._share_at(now)
        second = self._share_at(now)
        # First has no earlier neighbour → it notifies; second is suppressed.
        assert not SharedArticle.has_earlier_recent_share_to(self.recipient.id, first.id, 10)
        assert SharedArticle.has_earlier_recent_share_to(self.recipient.id, second.id, 10)

    def test_share_after_the_window_notifies_again(self):
        self._share_at(datetime.now() - timedelta(minutes=30))
        later = self._share_at(datetime.now())
        # The earlier share is outside the 10-min window → the later one notifies.
        assert not SharedArticle.has_earlier_recent_share_to(self.recipient.id, later.id, 10)

    def test_other_recipients_do_not_count(self):
        other = UserRule().user
        self._share_at(datetime.now())  # to self.recipient
        to_other = self._share_at(datetime.now(), to_user=other)
        assert not SharedArticle.has_earlier_recent_share_to(other.id, to_other.id, 10)
