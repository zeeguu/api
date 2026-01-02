"""
Unit tests for Multi-Word Expression (MWE) detector.

Tests particle verb detection using dependency parsing.
"""

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.tokenization import get_tokenizer, TokenizerModel
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.mwe.detector import (
    detect_particle_verbs,
    find_mwe_at_position,
    get_mwe_text
)


class MWEDetectorTest(ModelTestMixIn):
    """Test MWE detection functionality."""

    def setUp(self):
        super().setUp()
        self.da_lang = LanguageRule.get_or_create_language("da")
        self.de_lang = LanguageRule.get_or_create_language("de")

        # Use dependency parsing tokenizer
        self.tokenizer_model = TokenizerModel.STANZA_TOKEN_POS_DEP
        self.da_tokenizer = get_tokenizer(self.da_lang, self.tokenizer_model)
        self.de_tokenizer = get_tokenizer(self.de_lang, self.tokenizer_model)

    def test_danish_adjacent_particle_verb(self):
        """Test detection of Danish adjacent particle verb 'kom op'."""
        text = "Han kom op med en god idé"
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        particle_verbs = detect_particle_verbs(tokens)

        # Should find one particle verb
        assert len(particle_verbs) == 1

        pv = particle_verbs[0]
        assert pv['verb_text'] == 'kom'
        assert pv['verb_lemma'] == 'komme'
        assert pv['particle_texts'] == ['op']
        assert pv['type'] == 'particle_verb'
        assert pv['is_separated'] == False

        # Verb at position 1, particle at position 2
        assert pv['verb_position'] == 1
        assert pv['particle_positions'] == [2]
        assert pv['all_positions'] == [1, 2]

    def test_german_separated_particle_verb(self):
        """Test detection of German separated particle verb 'rufe...an'."""
        text = "Ich rufe dich morgen an"
        tokens = self.de_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        particle_verbs = detect_particle_verbs(tokens)

        # Should find one particle verb
        assert len(particle_verbs) == 1

        pv = particle_verbs[0]
        assert pv['verb_text'] == 'rufe'
        assert pv['verb_lemma'] == 'rufen'
        assert pv['particle_texts'] == ['an']
        assert pv['type'] == 'particle_verb'
        assert pv['is_separated'] == True

        # Verb at position 1, particle at position 4 (separated by 3 words)
        assert pv['verb_position'] == 1
        assert pv['particle_positions'] == [4]
        assert pv['all_positions'] == [1, 4]

    def test_find_mwe_at_verb_position(self):
        """Test finding MWE when user clicks the verb."""
        text = "Han kom op med en god idé"
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        # User clicks "kom" (position 1)
        mwe = find_mwe_at_position(tokens, 1)

        assert mwe is not None
        assert mwe['verb_text'] == 'kom'
        assert mwe['particle_texts'] == ['op']
        assert 1 in mwe['all_positions']
        assert 2 in mwe['all_positions']

    def test_find_mwe_at_particle_position(self):
        """Test finding MWE when user clicks the particle."""
        text = "Han kom op med en god idé"
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        # User clicks "op" (position 2)
        mwe = find_mwe_at_position(tokens, 2)

        assert mwe is not None
        assert mwe['verb_text'] == 'kom'
        assert mwe['particle_texts'] == ['op']

    def test_find_mwe_at_non_mwe_position(self):
        """Test that non-MWE words return None."""
        text = "Han kom op med en god idé"
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        # User clicks "Han" (position 0, not part of MWE)
        mwe = find_mwe_at_position(tokens, 0)

        assert mwe is None

    def test_get_mwe_text_adjacent(self):
        """Test MWE text formatting for adjacent particles."""
        text = "Han kom op med en god idé"
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        mwe = find_mwe_at_position(tokens, 1)
        mwe_text = get_mwe_text(tokens, mwe)

        # Adjacent particles should have simple space separation
        assert mwe_text == 'kom op'

    def test_get_mwe_text_separated(self):
        """Test MWE text formatting for separated particles."""
        text = "Ich rufe dich morgen an"
        tokens = self.de_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        mwe = find_mwe_at_position(tokens, 1)
        mwe_text = get_mwe_text(tokens, mwe)

        # Separated particles should have ellipsis
        assert mwe_text == 'rufe ... an'

    def test_no_particle_verbs_in_simple_sentence(self):
        """Test that simple sentences without particle verbs return empty list."""
        text = "Han er glad"  # "He is happy" - no particle verbs
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        particle_verbs = detect_particle_verbs(tokens)

        assert len(particle_verbs) == 0

    def test_dependency_fields_present_in_tokens(self):
        """Test that tokens have dependency parsing fields."""
        text = "Han kom op"
        tokens = self.da_tokenizer.tokenize_text(text, as_serializable_dictionary=False, flatten=True)

        # Check that all tokens have dependency fields
        for token in tokens:
            assert hasattr(token, 'dep')
            assert hasattr(token, 'head')
            assert hasattr(token, 'lemma')

        # Check specific token properties
        assert tokens[1].text == 'kom'
        assert tokens[1].lemma == 'komme'
        assert tokens[1].dep == 'root'

        assert tokens[2].text == 'op'
        assert tokens[2].dep == 'compound:prt'
        assert tokens[2].head == 2  # Points to 'kom' (1-based indexing)
