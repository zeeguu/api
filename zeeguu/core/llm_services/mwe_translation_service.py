"""
LLM-based translation service for separated MWEs.

When MWE words are not contiguous (e.g., "rufe dich an" where "dich"
separates "rufe" and "an"), traditional translation loses context.
This service uses Claude to translate the MWE with full sentence context.

Usage:
    from zeeguu.core.llm_services.mwe_translation_service import translate_separated_mwe

    translation = translate_separated_mwe(
        mwe_text="rufe...an",           # The MWE expression
        sentence="Ich rufe dich morgen an",  # Full sentence for context
        source_lang="German",
        target_lang="English"
    )
    # Returns: "call (phone)"
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Language code to name mapping
LANG_NAMES = {
    "de": "German", "da": "Danish", "nl": "Dutch", "sv": "Swedish", "no": "Norwegian",
    "el": "Greek", "it": "Italian", "es": "Spanish", "fr": "French", "ro": "Romanian",
    "pt": "Portuguese", "pl": "Polish", "ru": "Russian", "tr": "Turkish", "en": "English",
}

TRANSLATION_PROMPT = """Translate the multi-word expression (MWE) in context.

The MWE "{mwe_text}" appears in this {source_lang} sentence:
"{sentence}"

Translate ONLY the MWE to {target_lang}.
- Give a concise translation (1-3 words)
- The MWE parts may be separated in the sentence (e.g., "rufe...an" = anrufen)
- Consider the full sentence context for accurate translation

Return ONLY the translation, nothing else.

Translation:"""


def translate_separated_mwe(
    mwe_text: str,
    sentence: str,
    source_lang: str,
    target_lang: str = "en",
    timeout: int = 30
) -> Optional[str]:
    """
    Translate a separated MWE using Claude with sentence context.

    Args:
        mwe_text: The MWE expression (e.g., "rufe...an" or "rufe an")
        sentence: The full sentence containing the MWE
        source_lang: Source language code (e.g., "de") or name (e.g., "German")
        target_lang: Target language code (e.g., "en") or name (e.g., "English")
        timeout: API timeout in seconds

    Returns:
        Translation string, or None if translation failed
    """
    # Convert language codes to names
    source_name = LANG_NAMES.get(source_lang, source_lang)
    target_name = LANG_NAMES.get(target_lang, target_lang)

    prompt = TRANSLATION_PROMPT.format(
        mwe_text=mwe_text,
        sentence=sentence,
        source_lang=source_name,
        target_lang=target_name
    )

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, cannot translate separated MWE")
            return None

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Fast model for translation
            max_tokens=50,  # Short response expected
            temperature=0.1,  # Low temperature for consistent translation
            messages=[{"role": "user", "content": prompt}]
        )

        translation = response.content[0].text.strip()

        # Clean up translation (remove quotes, punctuation)
        translation = translation.strip('"\'.')

        logger.debug(f"Translated MWE '{mwe_text}' -> '{translation}'")
        return translation

    except ImportError:
        logger.error("anthropic package not installed")
        return None
    except Exception as e:
        logger.error(f"MWE translation failed: {e}")
        return None


def translate_separated_mwe_batch(
    mwes: list,
    sentence: str,
    source_lang: str,
    target_lang: str = "en",
    timeout: int = 60
) -> dict:
    """
    Translate multiple MWEs from the same sentence in one API call.

    Args:
        mwes: List of MWE texts (e.g., ["rufe...an", "gib...auf"])
        sentence: The full sentence containing the MWEs
        source_lang: Source language code
        target_lang: Target language code
        timeout: API timeout in seconds

    Returns:
        Dict mapping MWE text to translation
    """
    if not mwes:
        return {}

    # Convert language codes to names
    source_name = LANG_NAMES.get(source_lang, source_lang)
    target_name = LANG_NAMES.get(target_lang, target_lang)

    mwe_list = "\n".join(f"- {mwe}" for mwe in mwes)

    prompt = f"""Translate these multi-word expressions (MWEs) from {source_name} to {target_name}.

Sentence: "{sentence}"

MWEs to translate:
{mwe_list}

Return JSON mapping each MWE to its translation:
{{"mwe1": "translation1", "mwe2": "translation2"}}

JSON:"""

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {}

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text.strip()

        # Parse JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            content = content[start:end]

        return json.loads(content)

    except Exception as e:
        logger.error(f"Batch MWE translation failed: {e}")
        return {}
