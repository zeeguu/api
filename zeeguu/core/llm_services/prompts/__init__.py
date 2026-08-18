"""
Unified prompts module for all LLM-powered features in Zeeguu.
"""

from .example_generation import (
    example_sentence_fields,
    format_prompt,
    PROMPT_VERSION_V3,
)
from .meaning_frequency_classifier import (
    create_meaning_frequency_and_type_prompt,
    create_meaning_frequency_prompt,
    MEANING_FREQUENCY_AND_TYPE_PROMPT
)

__all__ = [
    'example_sentence_fields',
    'format_prompt',
    'PROMPT_VERSION_V3',
    'create_meaning_frequency_and_type_prompt',
    'create_meaning_frequency_prompt',
    'MEANING_FREQUENCY_AND_TYPE_PROMPT'
]