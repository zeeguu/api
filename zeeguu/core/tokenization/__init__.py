from .token import Token
from .stanza_tokenizer import StanzaTokenizer
from .nltk_tokenizer import NLTKTokenizer
from .zeeguu_tokenizer import TokenizerModel


"""
- NLTK is the fastest model.
- STANZA_TOKEN_ONLY has better accuracy, but is slightly slower
- STANZA_TOKEN_POS uses the same a TOKEN, but also does POS, much slower.
"""
TOKENIZER_MODEL = TokenizerModel.STANZA_TOKEN_ONLY


def get_tokenizer(language, model):
    if model in StanzaTokenizer.STANZA_MODELS:
        return StanzaTokenizer(language, model)
    else:
        return NLTKTokenizer(language)
