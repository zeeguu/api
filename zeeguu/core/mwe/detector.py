"""
MWE Detector - Identifies multi-word expressions in tokenized text.

This module adds MWE metadata to tokens, enabling the frontend to:
1. Highlight all MWE words when one is clicked
2. Translate the MWE as a unit
3. Create bookmarks that span multiple tokens

Usage:
    from zeeguu.core.mwe import enrich_article_with_mwe

    # After tokenization, enrich with MWE detection:
    tokenized = tokenizer.tokenize_text(content, flatten=False)
    enriched = enrich_article_with_mwe(tokenized, "de")

Each token gets enriched with:
    - mwe_group_id: str or None - unique ID linking MWE partners
    - mwe_role: "head" | "dependent" | None
    - mwe_type: "particle_verb" | "grammatical" | "negation" | None
    - mwe_is_separated: bool - True if MWE has non-MWE words between partners
      (e.g., "rufe dich an" where "dich" separates "rufe" and "an")
"""

import logging
from typing import List, Dict
from .strategies import get_strategy_for_language

logger = logging.getLogger(__name__)

# Languages that benefit from LLM validation (separable verbs, complex grammar)
HYBRID_LANGUAGES = {"de", "nl", "sv", "da", "no", "en", "el"}


class MWEDetector:
    """Detects multi-word expressions in tokenized sentences."""

    def __init__(self, language_code: str, mode: str = "stanza"):
        """
        Initialize MWE detector.

        Args:
            language_code: ISO language code (e.g., "de", "da")
            mode: Detection mode:
                - "stanza": Fast dependency-based (default, high recall)
                - "llm": Claude-based (high precision, slower)
                - "hybrid": Stanza + LLM validation (best accuracy, uses batch)
        """
        self.language_code = language_code
        self.mode = mode
        self.strategy = get_strategy_for_language(language_code, mode)

    def detect_in_paragraphs(self, tokenized_paragraphs: List[List[List[Dict]]]) -> List[List[List[Dict]]]:
        """
        Detect MWEs in all paragraphs.

        Args:
            tokenized_paragraphs: List of paragraphs, each containing sentences,
                                  each containing token dicts

        Returns:
            Same structure with MWE metadata added to tokens
        """
        logger.debug(f"MWE detection: mode={self.mode}, paragraphs={len(tokenized_paragraphs)}")

        # For hybrid mode, use batch processing (single LLM call for all sentences)
        if self.mode == "hybrid":
            return self._detect_batch(tokenized_paragraphs)

        # For other modes, process sentence by sentence
        for para_i, paragraph in enumerate(tokenized_paragraphs):
            for sent_i, sentence in enumerate(paragraph):
                mwe_groups = self.strategy.detect(sentence)
                self._apply_mwe_groups(sentence, mwe_groups, para_i, sent_i)

        return tokenized_paragraphs

    def _detect_batch(self, tokenized_paragraphs: List[List[List[Dict]]]) -> List[List[List[Dict]]]:
        """
        Batch detect MWEs using a single LLM call for all sentences.

        This is much more efficient than per-sentence processing.
        """
        from .llm_strategy import BatchHybridMWEStrategy

        # Flatten all sentences with their coordinates
        all_sentences = []  # [(para_i, sent_i, tokens)]
        for para_i, paragraph in enumerate(tokenized_paragraphs):
            for sent_i, sentence in enumerate(paragraph):
                all_sentences.append((para_i, sent_i, sentence))

        if not all_sentences:
            return tokenized_paragraphs

        # Run batch detection
        batch_strategy = BatchHybridMWEStrategy(self.language_code)
        tokens_list = [tokens for _, _, tokens in all_sentences]
        mwe_results = batch_strategy.detect_batch(tokens_list)

        # Apply results to tokens
        for idx, (para_i, sent_i, tokens) in enumerate(all_sentences):
            mwe_groups = mwe_results[idx] if idx < len(mwe_results) else []
            self._apply_mwe_groups(tokens, mwe_groups, para_i, sent_i)

        return tokenized_paragraphs

    def _apply_mwe_groups(self, tokens: List[Dict], mwe_groups: List[Dict], para_i: int, sent_i: int) -> None:
        """Apply MWE group metadata to tokens."""
        for group_idx, group in enumerate(mwe_groups):
            group_id = f"mwe_{para_i}_{sent_i}_{group_idx}"
            head_idx = group["head_idx"]
            dependent_indices = group["dependent_indices"]
            mwe_type = group["type"]

            # Calculate if MWE is separated (has non-MWE words between partners)
            all_indices = sorted([head_idx] + dependent_indices)
            is_separated = self._check_if_separated(all_indices)

            # Log for debugging (only at DEBUG level)
            if logger.isEnabledFor(logging.DEBUG):
                head_word = tokens[head_idx].get("text", "?") if 0 <= head_idx < len(tokens) else "?"
                dep_words = [tokens[i].get("text", "?") for i in dependent_indices if 0 <= i < len(tokens)]
                logger.debug(f"MWE found: {head_word}...{'+'.join(dep_words)} (type={mwe_type}, separated={is_separated})")

            # Mark head token
            if 0 <= head_idx < len(tokens):
                self._mark_token(tokens[head_idx], group_id, "head", mwe_type, is_separated)

            # Mark dependent tokens
            for dep_idx in dependent_indices:
                if 0 <= dep_idx < len(tokens):
                    self._mark_token(tokens[dep_idx], group_id, "dependent", mwe_type, is_separated)

    def _mark_token(self, token: Dict, group_id: str, role: str, mwe_type: str,
                    is_separated: bool) -> None:
        """Mark a single token with MWE metadata."""
        token["mwe_group_id"] = group_id
        token["mwe_role"] = role
        token["mwe_type"] = mwe_type
        token["mwe_is_separated"] = is_separated

    def _check_if_separated(self, indices: List[int]) -> bool:
        """
        Check if MWE tokens are separated (have gaps between them).

        Args:
            indices: Sorted list of token indices in the MWE

        Returns:
            True if there are gaps (non-contiguous), False if all adjacent
        """
        if len(indices) <= 1:
            return False

        for i in range(1, len(indices)):
            if indices[i] - indices[i - 1] > 1:
                return True  # Gap found

        return False  # All adjacent


def enrich_article_with_mwe(
    tokenized_paragraphs: List,
    language_code: str,
    mode: str = None
) -> List:
    """
    Convenience function to enrich an entire article with MWE detection.

    Call this after tokenizer.tokenize_text() to add MWE metadata.

    Args:
        tokenized_paragraphs: Output from tokenizer.tokenize_text(flatten=False)
        language_code: e.g., "de", "en", "es"
        mode: Detection mode (auto-selected based on language if not specified):
            - "stanza": Fast dependency-based (high recall)
            - "llm": Claude-based (high precision, slower)
            - "hybrid": Stanza + LLM validation (best accuracy, default for Germanic/Greek)

    Returns:
        Same structure with MWE metadata added to tokens that are part of MWEs
    """
    # Auto-select mode based on language if not specified
    # Germanic + Greek languages use hybrid for better precision
    # (Stanza alone makes errors like "har...tilbud" instead of "har...været")
    if mode is None:
        mode = "hybrid" if language_code in HYBRID_LANGUAGES else "stanza"

    logger.info(f"MWE enrichment: lang={language_code}, mode={mode}")

    detector = MWEDetector(language_code, mode)
    return detector.detect_in_paragraphs(tokenized_paragraphs)
