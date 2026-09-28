import os
from .token import Token
from .zeeguu_tokenizer import TokenizerModel

# Imported lazily so that code which only needs NLTK doesn't pull in requests
_StanzaServiceClient = None
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

_STANZA_MODELS = {TokenizerModel.STANZA_TOKEN_ONLY, TokenizerModel.STANZA_TOKEN_POS, TokenizerModel.STANZA_TOKEN_POS_DEP}


def get_tokenizer(language, model):
    """Stanza always runs in the Stanza service (stanza_service/), never in
    this process: loading its models here cost every API worker gigabytes.
    Without STANZA_SERVICE_URL the client refuses to construct."""
    global _StanzaServiceClient, _NLTKTokenizer

    if model in _STANZA_MODELS:
        if _StanzaServiceClient is None:
            from .stanza_client import StanzaServiceClient
            _StanzaServiceClient = StanzaServiceClient
        return _StanzaServiceClient(language, model)

    if _NLTKTokenizer is None:
        from .nltk_tokenizer import NLTKTokenizer
        _NLTKTokenizer = NLTKTokenizer
    return _NLTKTokenizer(language)
