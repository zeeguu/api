from .token import Token
from .stanza_tokenizer import StanzaTokenizer
from .nltk_tokenizer import NLTKTokenizer
from .zeeguu_tokenizer import TokenizerModel


"""
- NLTK is the fastest model.
- STANZA_TOKEN_ONLY has better accuracy, but is slightly slower
- STANZA_TOKEN_POS uses the same as TOKEN, but also does POS, slower.
- STANZA_TOKEN_POS_DEP includes dependency parsing for MWE detection.
"""
# Using POS_DEP to enable MWE (Multi-Word Expression) detection
# This adds dep, head, lemma fields needed for particle verb detection
TOKENIZER_MODEL = TokenizerModel.STANZA_TOKEN_POS_DEP


def get_tokenizer(language, model):
    if model in StanzaTokenizer.STANZA_MODELS:
        return StanzaTokenizer(language, model)
    else:
        return NLTKTokenizer(language)
