"""
Azure Alignment-Based Contextual Translator

This module provides word translation using Azure's word alignment feature.
Unlike the span-tag approach (which relies on the translation API preserving
tag positions), alignment explicitly maps source words to target words.

Example:
    "har altså været" -> "has thus been"
    Alignment: 0:2-0:2 4:8-4:7 10:14-9:12
    (har->has, altså->thus, været->been)

This is more reliable than Google's span-tag approach which often moves
the span to the wrong word in the translation.
"""

import logging
import os
import re
from typing import Optional, Tuple, List

from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient

logger = logging.getLogger(__name__)


def _get_azure_client() -> TextTranslationClient:
    """Get Azure Text Translation client."""
    key = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")
    if not key:
        raise ValueError("MICROSOFT_TRANSLATE_API_KEY not set")

    credential = AzureKeyCredential(key)
    return TextTranslationClient(credential=credential)


def _parse_alignment(alignment_proj: str) -> list[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """
    Parse Azure alignment projection string.

    Format: "0:2-0:2 4:8-4:7 10:14-9:12"
    Each mapping is "src_start:src_end-tgt_start:tgt_end"

    Returns list of ((src_start, src_end), (tgt_start, tgt_end)) tuples.
    """
    mappings = []
    if not alignment_proj:
        return mappings

    for mapping in alignment_proj.split():
        try:
            src_part, tgt_part = mapping.split("-")
            src_start, src_end = map(int, src_part.split(":"))
            tgt_start, tgt_end = map(int, tgt_part.split(":"))
            mappings.append(((src_start, src_end), (tgt_start, tgt_end)))
        except (ValueError, AttributeError):
            continue

    return mappings


def _find_word_position(sentence: str, word: str) -> Optional[Tuple[int, int]]:
    """
    Find the position of a word in a sentence.
    Returns (start_char, end_char) or None if not found.

    Handles case-insensitive matching and strips punctuation.
    """
    word_lower = word.lower().strip()
    sentence_lower = sentence.lower()

    # Try to find as a whole word (word boundaries)
    pattern = r'\b' + re.escape(word_lower) + r'\b'
    match = re.search(pattern, sentence_lower)
    if match:
        return (match.start(), match.end() - 1)

    # Fallback: simple substring search
    idx = sentence_lower.find(word_lower)
    if idx >= 0:
        return (idx, idx + len(word_lower) - 1)

    return None


def translate_word_with_alignment(
    sentence: str,
    word: str,
    source_lang: str,
    target_lang: str
) -> Optional[dict]:
    """
    Translate a word in context using Azure's word alignment feature.

    Args:
        sentence: The full sentence containing the word
        word: The word to translate (can be multi-word)
        source_lang: Source language code (e.g., "da", "de")
        target_lang: Target language code (e.g., "en")

    Returns:
        dict with 'translation', 'source', 'likelihood' keys, or None if failed

    Example:
        translate_word_with_alignment(
            "Meningen med dette tiltag har altså været at få vaccineret",
            "altså",
            "da", "en"
        )
        -> {'translation': 'thus', 'source': 'Microsoft - alignment', 'likelihood': 90}
    """
    try:
        # Find word position in source sentence
        word_pos = _find_word_position(sentence, word)
        if not word_pos:
            logger.debug(f"Word '{word}' not found in sentence")
            return None

        src_start, src_end = word_pos

        # Translate with alignment
        client = _get_azure_client()
        response = client.translate(
            body=[sentence],
            to_language=[target_lang],
            from_language=source_lang,
            include_alignment=True
        )

        if not response or not response[0].translations:
            logger.debug("No translation response from Azure")
            return None

        translation_result = response[0].translations[0]
        translated_sentence = translation_result.text
        alignment = translation_result.alignment

        if not alignment or not alignment.proj:
            logger.debug("No alignment data in Azure response")
            return None

        # Parse alignment mappings
        mappings = _parse_alignment(alignment.proj)

        # Find all mappings that overlap with our word
        word_translations = []
        for (s_start, s_end), (t_start, t_end) in mappings:
            if s_start <= src_end and s_end >= src_start:
                target_word = translated_sentence[t_start:t_end + 1]
                word_translations.append((t_start, target_word))

        if not word_translations:
            logger.debug(f"No alignment found for word position {src_start}-{src_end}")
            return None

        # Sort by position and join (in case of multi-word translation)
        word_translations.sort(key=lambda x: x[0])
        translation = " ".join(t[1] for t in word_translations).strip()

        if not translation:
            return None

        logger.debug(f"Alignment translation: '{word}' -> '{translation}'")

        return {
            "translation": translation,
            "source": "Microsoft - alignment",
            "likelihood": 90,
            "service_name": "Microsoft - alignment"
        }

    except Exception as e:
        logger.warning(f"Alignment translation error: {e}")
        return None


def azure_alignment_translate(data: dict) -> Optional[dict]:
    """
    Compatibility wrapper for the translator pipeline.

    Args:
        data: dict with 'source_language', 'target_language', 'word', 'context' keys

    Returns:
        dict with 'translation', 'source', 'likelihood' keys
    """
    word = data.get("word", "")
    context = data.get("context", "")
    source_lang = data.get("source_language", "")
    target_lang = data.get("target_language", "")

    if not context:
        # No context - can't use alignment (need sentence)
        return None

    return translate_word_with_alignment(
        sentence=context,
        word=word,
        source_lang=source_lang,
        target_lang=target_lang
    )
