from unittest import TestCase

from zeeguu.core.mwe.stanza_mwe_detector import GermanicStrategy


def tok(text, pos, dep=None, head=None):
    return {"text": text, "pos": pos, "dep": dep, "head": head, "lemma": text}


class ArticleNounMWETest(TestCase):
    def setUp(self):
        self.strategy = GermanicStrategy()

    def test_article_noun_detected(self):
        # "en kikkert" -> head=kikkert (index 2 -> 1-based), en's head=2 (kikkert)
        tokens = [
            tok("Med", "ADP", dep="case", head=3),
            tok("en", "DET", dep="det", head=3),
            tok("kikkert", "NOUN", dep="obl", head=0),
        ]
        groups = self.strategy.detect(tokens)
        article_groups = [g for g in groups if g["type"] == "article_noun"]
        self.assertEqual(len(article_groups), 1)
        g = article_groups[0]
        self.assertEqual(g["head_idx"], 2)  # kikkert
        self.assertIn(1, g["dependent_indices"])  # en

    def test_det_pointing_at_non_noun_not_grouped(self):
        # "den" pointing at an adjective should not produce article_noun
        tokens = [
            tok("den", "DET", dep="det", head=2),
            tok("røde", "ADJ", dep="amod", head=0),
        ]
        groups = self.strategy.detect(tokens)
        article_groups = [g for g in groups if g["type"] == "article_noun"]
        self.assertEqual(len(article_groups), 0)

    def test_article_adj_noun_includes_adjective_via_postprocess(self):
        # "en lille prik" — DET+ADJ+NOUN, adjective sits between in indices.
        # Post-processing for separated MWEs pulls it in (gap of 1 word).
        tokens = [
            tok("en", "DET", dep="det", head=3),
            tok("lille", "ADJ", dep="amod", head=3),
            tok("prik", "NOUN", dep="obl", head=0),
        ]
        groups = self.strategy.detect(tokens)
        article_groups = [g for g in groups if g["type"] == "article_noun"]
        self.assertEqual(len(article_groups), 1)
        g = article_groups[0]
        self.assertEqual(g["head_idx"], 2)  # prik
        # Both 0 (en) and 1 (lille) should end up in dependent_indices —
        # 0 directly from the det relation, 1 via the gap-fill post-process.
        self.assertEqual(set(g["dependent_indices"]), {0, 1})

    def test_no_det_no_article_noun(self):
        tokens = [
            tok("Venus", "PROPN", dep="nsubj", head=2),
            tok("lyser", "VERB", dep="root", head=0),
        ]
        groups = self.strategy.detect(tokens)
        self.assertEqual([g for g in groups if g["type"] == "article_noun"], [])
