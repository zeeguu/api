from unittest import TestCase

from zeeguu.core.mwe.stanza_mwe_detector import GermanicStrategy


def tok(text, pos, dep=None, head=None):
    return {"text": text, "pos": pos, "dep": dep, "head": head, "lemma": text}


def particle_groups(tokens):
    return [g for g in GermanicStrategy().detect(tokens) if g["type"] == "particle_verb"]


class ParticleVerbMWETest(TestCase):
    def test_particle_in_another_clause_is_not_grouped(self):
        # Stanza's actual parse of "Den ser stor ud, fordi den er tæt på
        # Jorden.": it made "tæt" the particle of "ser", across the comma.
        tokens = [
            tok("Den", "PRON", "nsubj", 2),
            tok("ser", "VERB", "root", 0),
            tok("stor", "ADJ", "amod", 2),
            tok("ud", "ADV", "advmod", 2),
            tok(",", "PUNCT", "punct", 9),
            tok("fordi", "SCONJ", "mark", 9),
            tok("den", "PRON", "nsubj", 9),
            tok("er", "AUX", "cop", 9),
            tok("tæt", "ADV", "compound:prt", 2),
            tok("på", "ADP", "case", 11),
            tok("Jorden", "NOUN", "obl", 9),
            tok(".", "PUNCT", "punct", 2),
        ]
        self.assertEqual(particle_groups(tokens), [])

    def test_separated_particle_in_the_same_clause_is_grouped(self):
        # "Han står hver morgen op"
        tokens = [
            tok("Han", "PRON", "nsubj", 2),
            tok("står", "VERB", "root", 0),
            tok("hver", "DET", "det", 4),
            tok("morgen", "NOUN", "obl", 2),
            tok("op", "ADP", "compound:prt", 2),
        ]
        groups = particle_groups(tokens)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["head_idx"], 1)
        self.assertIn(4, groups[0]["dependent_indices"])

    def test_auxiliary_between_particle_and_verb_is_fine(self):
        # Dutch "omdat hij op zal staan"
        tokens = [
            tok("omdat", "SCONJ", "mark", 5),
            tok("hij", "PRON", "nsubj", 5),
            tok("op", "ADP", "compound:prt", 5),
            tok("zal", "AUX", "aux", 5),
            tok("staan", "VERB", "root", 0),
        ]
        groups = particle_groups(tokens)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["head_idx"], 4)
        self.assertIn(2, groups[0]["dependent_indices"])

    def test_an_aside_between_verb_and_particle_is_fine(self):
        # German "Er steht, wie immer, früh auf": commas, but no new verb
        tokens = [
            tok("Er", "PRON", "nsubj", 2),
            tok("steht", "VERB", "root", 0),
            tok(",", "PUNCT", "punct", 5),
            tok("wie", "ADP", "case", 5),
            tok("immer", "ADV", "advmod", 2),
            tok(",", "PUNCT", "punct", 5),
            tok("früh", "ADJ", "advmod", 2),
            tok("auf", "ADP", "compound:prt", 2),
        ]
        self.assertEqual(len(particle_groups(tokens)), 1)

    def test_a_comparison_between_verb_and_particle_is_fine(self):
        # Dutch "Hij ziet er als een kind uit": Stanza tags "als" SCONJ
        tokens = [
            tok("Hij", "PRON", "nsubj", 2),
            tok("ziet", "VERB", "root", 0),
            tok("er", "ADV", "advmod", 2),
            tok("als", "SCONJ", "mark", 6),
            tok("een", "DET", "det", 6),
            tok("kind", "NOUN", "obl", 2),
            tok("uit", "ADP", "compound:prt", 2),
        ]
        self.assertEqual(len(particle_groups(tokens)), 1)
