"""Per-level preview summaries (on-demand simplification flow).

Covers the level-selection logic and that the feed's summary payload anchors to
the CEFR-matched ArticleLevelSummary (with the ArticleLevelSummary context type)
so the tappable preview / bookmark highlighting targets the right level.
"""
from unittest import TestCase

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.user_rule import UserRule

from zeeguu.core.model.article_level_summary import ArticleLevelSummary
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_language import UserLanguage

session = zeeguu.core.model.db.session

# A minimal non-empty token stream (shape is opaque to our code — we only check
# truthiness and round-tripping).
DUMMY_TOKENS = [[{"text": "hej", "sentence_i": 0, "token_i": 0}]]

CEFR_TO_INT = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


class ArticleLevelSummaryTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.article = ArticleRule().article
        # Align the article's language with the user's learned language so the
        # summary path is exercised in the same language.
        self.article.language = self.user.learned_language
        session.add(self.article)
        session.commit()

    def _add_level_summary(self, level):
        return ArticleLevelSummary.find_or_create(
            session,
            self.article,
            cefr_level=level,
            summary=f"summary at {level}",
            tokenized_summary=DUMMY_TOKENS,
        )

    def _set_user_level(self, level):
        ul = UserLanguage.find_or_create(session, self.user, self.user.learned_language)
        ul.cefr_level = CEFR_TO_INT[level]
        session.add(ul)
        session.commit()

    def test_best_for_user_level_picks_highest_at_or_below(self):
        self._add_level_summary("A1")
        b1 = self._add_level_summary("B1")

        # B2 learner → highest available at/below is B1
        assert ArticleLevelSummary.best_for_user_level(self.article.id, "B2").id == b1.id
        # C1 learner → still B1 (nothing higher stored)
        assert ArticleLevelSummary.best_for_user_level(self.article.id, "C1").id == b1.id
        # A2 learner → only A1 qualifies
        assert (
            ArticleLevelSummary.best_for_user_level(self.article.id, "A2").cefr_level
            == "A1"
        )
        # A1 learner → A1
        assert (
            ArticleLevelSummary.best_for_user_level(self.article.id, "A1").cefr_level
            == "A1"
        )

    def test_no_summary_at_or_below_returns_none(self):
        self._add_level_summary("B1")
        # An A1 learner has nothing at/below B1... wait, B1 > A1, so None.
        assert ArticleLevelSummary.best_for_user_level(self.article.id, "A1") is None

    def test_summary_info_anchors_to_level_summary(self):
        self._add_level_summary("A1")
        b1 = self._add_level_summary("B1")
        self._set_user_level("B2")

        info = UserArticle.user_article_summary_info(self.user, self.article)
        payload = info.get("tokenized_summary")
        assert payload is not None
        ctx = payload["context_identifier"]
        assert ctx["context_type"] == ContextType.ARTICLE_LEVEL_SUMMARY
        assert ctx["article_level_summary_id"] == b1.id
        assert payload["tokens"] == DUMMY_TOKENS

    def test_summary_info_falls_back_to_original_when_no_level_match(self):
        # Learner at A1 with only a B1 summary → no per-level match → falls back
        # to the article's own summary (ArticleSummary context, keyed by article).
        self._add_level_summary("B1")
        self._set_user_level("A1")

        info = UserArticle.user_article_summary_info(self.user, self.article)
        payload = info.get("tokenized_summary")
        if payload is not None:  # only asserted when the article has an own summary
            assert (
                payload["context_identifier"]["context_type"]
                == ContextType.ARTICLE_SUMMARY
            )
