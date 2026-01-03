from .token import Token
from .zeeguu_tokenizer import TokenizerModel

# Lazy imports to avoid loading stanza/torch at startup (~2s savings)
_StanzaTokenizer = None
_NLTKTokenizer = None

"""
- NLTK is the fastest model.
- STANZA_TOKEN_ONLY has better accuracy, but is slightly slower
- STANZA_TOKEN_POS uses the same as TOKEN, but also does POS, slower.
- STANZA_TOKEN_POS_DEP includes dependency parsing for MWE detection.
"""
# Using POS_DEP to enable MWE (Multi-Word Expression) detection
# This adds dep, head, lemma fields needed for particle verb detection
TOKENIZER_MODEL = TokenizerModel.STANZA_TOKEN_POS_DEP

# Stanza model types (duplicated here to avoid importing StanzaTokenizer)
_STANZA_MODELS = {TokenizerModel.STANZA_TOKEN_ONLY, TokenizerModel.STANZA_TOKEN_POS, TokenizerModel.STANZA_TOKEN_POS_DEP}


def get_tokenizer(language, model):
    global _StanzaTokenizer, _NLTKTokenizer

    if model in _STANZA_MODELS:
        if _StanzaTokenizer is None:
            from .stanza_tokenizer import StanzaTokenizer
            _StanzaTokenizer = StanzaTokenizer
        return _StanzaTokenizer(language, model)
    else:
        if _NLTKTokenizer is None:
            from .nltk_tokenizer import NLTKTokenizer
            _NLTKTokenizer = NLTKTokenizer
        return _NLTKTokenizer(language)
