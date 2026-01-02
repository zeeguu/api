# MWE (Multi-Word Expression) Detection Module
#
# This module detects multi-word expressions like:
# - Particle verbs: "ruft...an" (calls), "steht...auf" (gets up)
# - Grammatical: "il y a" (there is), "wird kommen" (will come)
# - Phrasal verbs: "llevó a cabo" (carried out)
#
# Detection modes:
# - "stanza": Fast dependency-based (default, high recall)
# - "llm": Claude-based (high precision, slower)
# - "hybrid": Stanza + LLM validation (best accuracy)
#
# Usage:
#     from zeeguu.core.mwe import tokenize_for_reading
#     tokens = tokenize_for_reading(text, language)

from .detector import MWEDetector, enrich_tokens_with_mwe
from .strategies import get_strategy_for_language


def tokenize_for_reading(text, language, flatten=False, mode=None, **kwargs):
    """
    Tokenize text with MWE enrichment for interactive reading.

    Use this when tokenizing text that users will interact with (click to translate).
    Combines tokenization + MWE detection in one call.

    Args:
        text: The text to tokenize
        language: Language object
        flatten: If False, returns paragraphs->sentences->tokens structure
        mode: MWE detection mode ("stanza", "llm", "hybrid", or None for auto)
        **kwargs: Additional args passed to tokenize_text (start_token_i, etc.)

    Returns:
        Tokenized text with MWE metadata
    """
    from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL

    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
    tokens = tokenizer.tokenize_text(text, flatten=flatten, **kwargs)

    if not flatten:
        # MWE enrichment requires paragraph structure
        tokens = enrich_tokens_with_mwe(tokens, language.code, mode=mode)

    return tokens


__all__ = ["MWEDetector", "enrich_tokens_with_mwe", "tokenize_for_reading", "get_strategy_for_language"]
