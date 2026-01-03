"""
Translation services for Zeeguu.

This module provides translation functionality using various APIs:
- Google Translate
- Microsoft/Azure Translator (with word alignment)
- Wordnik (for English definitions)
"""

from .translator import (
    get_all_translations,
    get_next_results,
    get_best_translation,
    contribute_trans,
)

from .azure_alignment import azure_alignment_translate
