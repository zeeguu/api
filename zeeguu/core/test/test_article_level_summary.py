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
from zeeguu.core.model.article_level_summary_context import ArticleLevelSummaryContext
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_language import UserLanguage
from zeeguu.core.model.user_mwe_override import UserMweOverride
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule

session = zeeguu.core.model.db.session

# A minimal non-empty token stream in the real shape: paragraphs -> sentences ->
# tokens (same nesting tokenize_for_reading produces).
DUMMY_TOKENS = [[[{"text": "hej", "sentence_i": 0, "token_i": 0}]]]

# A summary token stream (paragraphs -> sentences -> tokens) whose first sentence
# groups "har lavet" into an MWE. The metadata keys mirror what
# UserArticle._clear_mwe_metadata_for_expressions reads and clears.
MWE_SENTENCE_TEXT = "har lavet mad"
MWE_EXPRESSION = "har lavet"


def _mwe_tokens():
    return [
        [
            [
                {"text": "har", "sentence_i": 0, "token_i": 0, "mwe_group_id": 7,
                 "mwe_role": "head", "mwe_is_separated": False,
                 "mwe_partner_indices": [1]},
                {"text": "lavet", "sentence_i": 0, "token_i": 1, "mwe_group_id": 7,
                 "mwe_role": "dep", "mwe_is_separated": False,
                 "mwe_partner_indices": [0]},
                {"text": "mad", "sentence_i": 0, "token_i": 2},
            ]
        ]
    ]


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

    def _add_mwe_level_summary(self, level):
        return ArticleLevelSummary.find_or_create(
            session,
            self.article,
            cefr_level=level,
            summary=f"summary at {level}",
            tokenized_summary=_mwe_tokens(),
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

    def test_learner_at_or_above_article_level_gets_the_articles_own_summary(self):
        """
        Rows exist only BELOW the article's own level, so a learner reading at or
        above it must fall through to Article.summary (None here) rather than be
        handed the highest stored row.

        This is the Danish B1 collapse: 366 of 368 recent Danish B1 articles carry
        only A1 and A2 rows, so before this every reader from B1 up was served the
        A2 summary and changing CEFR level changed nothing on the card.
        """
        self._add_level_summary("A1")
        self._add_level_summary("A2")

        for level_at_or_above in ("B1", "B2", "C1", "C2"):
            assert (
                ArticleLevelSummary.best_for_user_level(
                    self.article.id, level_at_or_above, "B1"
                )
                is None
            ), f"{level_at_or_above} learner should get the article's own summary"

        # ...while learners below the article's level still get their own row,
        # and crucially A2 and B1 no longer collapse onto the same text.
        assert (
            ArticleLevelSummary.best_for_user_level(self.article.id, "A2", "B1").cefr_level
            == "A2"
        )
        assert (
            ArticleLevelSummary.best_for_user_level(self.article.id, "A1", "B1").cefr_level
            == "A1"
        )

    def test_own_level_summary_preferred_over_a_simpler_row(self):
        """An A2 learner on an A2 article gets the article's own A2 summary, not
        the A1 row that happens to be the highest stored one at/below A2."""
        self._add_level_summary("A1")
        assert ArticleLevelSummary.best_for_user_level(self.article.id, "A2", "A2") is None
        assert (
            ArticleLevelSummary.best_for_user_level(self.article.id, "A1", "A2").cefr_level
            == "A1"
        )

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

    def test_level_summary_context_carries_parent_article_id(self):
        # The served level-summary context now also carries the parent article id
        # so the client's MWE-ungroup path can address the override.
        self._add_level_summary("B1")
        self._set_user_level("B2")

        info = UserArticle.user_article_summary_info(self.user, self.article)
        ctx = info["tokenized_summary"]["context_identifier"]
        assert ctx["context_type"] == ContextType.ARTICLE_LEVEL_SUMMARY
        assert ctx["article_id"] == self.article.id

    def test_mwe_override_clears_metadata_on_level_summary(self):
        # A B2 learner served a B1 level summary whose first sentence groups
        # "har lavet" as an MWE. After the user ungroups it (an override keyed by
        # the parent article id + sentence hash), the served summary tokens must
        # have the MWE metadata stripped.
        self._add_mwe_level_summary("B1")
        self._set_user_level("B2")

        sentence_hash = UserMweOverride.compute_sentence_hash(MWE_SENTENCE_TEXT)
        UserMweOverride.find_or_create(
            session,
            user_id=self.user.id,
            article_id=self.article.id,
            sentence_hash=sentence_hash,
            mwe_expression=MWE_EXPRESSION,
        )
        session.commit()

        info = UserArticle.user_article_summary_info(self.user, self.article)
        tokens = info["tokenized_summary"]["tokens"]
        sentence = tokens[0][0]

        # The two MWE tokens are stripped of all mwe_* metadata...
        for tok in sentence[:2]:
            assert "mwe_group_id" not in tok
            assert "mwe_role" not in tok
            assert "mwe_is_separated" not in tok
            assert "mwe_partner_indices" not in tok
        # ...while the untouched token keeps its plain text.
        assert sentence[2]["text"] == "mad"

    def test_mwe_override_untouched_when_expression_not_disabled(self):
        # Sanity: with no matching override, the MWE metadata survives.
        self._add_mwe_level_summary("B1")
        self._set_user_level("B2")

        info = UserArticle.user_article_summary_info(self.user, self.article)
        sentence = info["tokenized_summary"]["tokens"][0][0]
        assert sentence[0]["mwe_group_id"] == 7

    def test_mwe_override_does_not_mutate_stored_tokens(self):
        # The served tokens are a cleared copy; the ArticleLevelSummary row's own
        # tokenized_summary must be left intact (no accidental DB-side mutation).
        als = self._add_mwe_level_summary("B1")
        self._set_user_level("B2")
        UserMweOverride.find_or_create(
            session,
            user_id=self.user.id,
            article_id=self.article.id,
            sentence_hash=UserMweOverride.compute_sentence_hash(MWE_SENTENCE_TEXT),
            mwe_expression=MWE_EXPRESSION,
        )
        session.commit()

        UserArticle.user_article_summary_info(self.user, self.article)

        # The stored row still has its MWE grouping.
        assert als.get_tokenized_summary()[0][0][0]["mwe_group_id"] == 7

    def test_overlay_applies_mwe_override_and_carries_article_id(self):
        # Exercise the feed overlay path directly (not just user_article_summary_info).
        from zeeguu.core.content_recommender.elastic_recommender import (
            _apply_simplified_display_overlay,
        )

        self._add_mwe_level_summary("B1")
        self._set_user_level("B2")
        UserMweOverride.find_or_create(
            session,
            user_id=self.user.id,
            article_id=self.article.id,
            sentence_hash=UserMweOverride.compute_sentence_hash(MWE_SENTENCE_TEXT),
            mwe_expression=MWE_EXPRESSION,
        )
        session.commit()

        results = [{"id": self.article.id}]
        _apply_simplified_display_overlay(self.user, results)

        interactive = results[0].get("interactiveSummary")
        assert interactive is not None
        ctx = interactive["context_identifier"]
        assert ctx["context_type"] == ContextType.ARTICLE_LEVEL_SUMMARY
        assert ctx["article_id"] == self.article.id
        # MWE metadata cleared on the overlaid tokens.
        sentence = interactive["tokens"][0][0]
        assert "mwe_group_id" not in sentence[0]
        assert "mwe_group_id" not in sentence[1]

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

    def test_context_find_or_create_is_idempotent(self):
        als = self._add_level_summary("B1")
        bookmark = BookmarkRule(self.user).bookmark

        c1 = ArticleLevelSummaryContext.find_or_create(session, bookmark, als)
        c2 = ArticleLevelSummaryContext.find_or_create(session, bookmark, als)

        assert c1.id == c2.id
        count = ArticleLevelSummaryContext.query.filter_by(
            bookmark_id=bookmark.id, article_level_summary_id=als.id
        ).count()
        assert count == 1

    def test_duplicate_context_rejected_by_unique_constraint(self):
        from sqlalchemy.exc import IntegrityError

        als = self._add_level_summary("B1")
        bookmark = BookmarkRule(self.user).bookmark

        # Two raw rows for the same (bookmark, level summary) must not coexist.
        session.add(ArticleLevelSummaryContext(bookmark, als))
        session.add(ArticleLevelSummaryContext(bookmark, als))
        with self.assertRaises(IntegrityError):
            session.flush()
        session.rollback()
