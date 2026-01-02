# MWE (Multi-Word Expression) Detection Module
#
# This module detects multi-word expressions like:
# - Particle verbs: "steht...auf" (gets up), "gives...up"
# - Grammatical: "wird kommen" (will come), "has eaten"
# - Negation: "geht nicht" (doesn't go)
#
# Detection modes:
# - "stanza": Fast dependency-based (default, high recall)
# - "llm": Claude-based (high precision, slower)
# - "hybrid": Stanza + LLM validation (best accuracy)
#
# Usage:
#     from zeeguu.core.mwe import enrich_article_with_mwe
#     tokenized = tokenizer.tokenize_text(content, flatten=False)
#
#     # Default (Stanza-based, fast)
#     enriched = enrich_article_with_mwe(tokenized, "de")
#
#     # LLM-based (high precision)
#     enriched = enrich_article_with_mwe(tokenized, "de", mode="llm")
#
#     # Hybrid (best accuracy)
#     enriched = enrich_article_with_mwe(tokenized, "de", mode="hybrid")

from .detector import MWEDetector, enrich_article_with_mwe
from .strategies import get_strategy_for_language

__all__ = ["MWEDetector", "enrich_article_with_mwe", "get_strategy_for_language"]
