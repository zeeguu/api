from .token import Token
from .tokenizer import ZeeguuTokenizer, TokenizerModel

"""
- NLTK is the fastest model.
- STANZA_TOKEN_ONLY has better accuracy, but is slightly slower
- STANZA_TOKEN_POS uses the same a TOKEN, but also does POS, much slower.
"""
TOKENIZER_MODEL = TokenizerModel.STANZA_TOKEN_ONLY
