"""
Voice configuration for audio lessons.
Maps voice names and languages to Google Cloud Text-to-Speech voice IDs.
"""

# Voice mappings for different languages
VOICE_CONFIG = {
    "da-DK": {"woman": "da-DK-Wavenet-A", "man": "da-DK-Wavenet-G"},  # Danish
    "es-ES": {  # Spanish
        "woman": "es-ES-Chirp3-HD-Aoede",
        "man": "es-ES-Chirp3-HD-Algenib",
    },
    "it-IT": {"woman": "it-IT-Wavenet-A", "man": "it-IT-Wavenet-D"},  # Italian
    "pt-PT": {  # Portuguese (European)
        "woman": "pt-PT-Wavenet-E",
        "man": "pt-PT-Wavenet-F",
    },
    "fr-FR": {  # French (France)
        "woman": "fr-FR-Chirp3-HD-Sulafat",
        "man": "fr-FR-Chirp3-HD-Algenib",
    },
    "de-DE": {  # German (Germany)
        "woman": "de-DE-Chirp3-HD-Aoede",
        "man": "de-DE-Chirp3-HD-Enceladus",
        # others good women: de-DE-Chirp3-HD-Gacrux, de-DE-Chirp3-HD-Sulafat
        # others good men: de-DE-Chirp3-HD-Algenib, de-DE-Chirp3-HD-Sadachbia
    },
    "nl-NL": {  # Dutch (Netherlands)
        "woman": "nl-NL-Chirp3-HD-Aoede",
        "man": "nl-NL-Chirp3-HD-Enceladus",  # nl-NL-Chirp3-HD-Algieba
    },
    "sv-SE": {"woman": "sv-SE-Standard-F", "man": "sv-SE-Standard-G"},  # Swedish
    "en-US": {  # English
        "teacher": "en-US-Wavenet-J",
        "man": "en-US-Wavenet-D",
        "woman": "en-US-Wavenet-F",
    },
    "ro-RO": {  # Romanian
        "woman": "ro-RO-Wavenet-A",
        "man": "ro-RO-Standard-A",
        "teacher": "ro-RO-Wavenet-A",  # Teacher voice in Romanian
    },
}

# Default silence duration between sentences (in seconds)
DEFAULT_SILENCE_SECONDS = 5.0

# Language code mappings from short codes to full locale codes
LANGUAGE_MAPPINGS = {
    "da": "da-DK",
    "es": "es-ES",
    "it": "it-IT",
    "fr": "fr-FR",
    "de": "de-DE",
    "nl": "nl-NL",
    "sv": "sv-SE",
    "en": "en-US",
    "pt": "pt-PT",
    "ro": "ro-RO",
}


def normalize_language_code(language_code: str) -> str:
    """
    Convert short language codes to full locale codes.

    Args:
        language_code: Short code like 'it', 'da' or full code like 'it-IT'

    Returns:
        Full locale code like 'it-IT', 'da-DK'
    """
    # If already a full locale code, return as is
    if "-" in language_code:
        return language_code

    # Convert short code to full locale code
    if language_code in LANGUAGE_MAPPINGS:
        return LANGUAGE_MAPPINGS[language_code]

    raise ValueError(
        f"Language {language_code} not supported. Available: {list(LANGUAGE_MAPPINGS.keys())}"
    )


def get_voice_id(language_code: str, voice_name: str) -> str:
    """
    Get the Google Cloud TTS voice ID for a given language and voice name.

    Args:
        language_code: Language code like 'da', 'it' or 'da-DK', 'it-IT', etc.
        voice_name: Voice name like 'man', 'woman', 'teacher'

    Returns:
        Google Cloud TTS voice ID

    Raises:
        ValueError: If language or voice not found in configuration
    """
    # Normalize the language code
    full_language_code = normalize_language_code(language_code)

    if full_language_code not in VOICE_CONFIG:
        raise ValueError(
            f"Language {language_code} not supported. Available: {list(VOICE_CONFIG.keys())}"
        )

    if voice_name not in VOICE_CONFIG[full_language_code]:
        available_voices = list(VOICE_CONFIG[full_language_code].keys())
        raise ValueError(
            f"Voice {voice_name} not available for {full_language_code}. Available: {available_voices}"
        )

    return VOICE_CONFIG[full_language_code][voice_name]


def get_teacher_voice() -> str:
    """Get the teacher voice ID (always English)."""
    return get_voice_id("en-US", "teacher")


def get_language_voices(language_code: str) -> dict:
    """Get all available voices for a language."""
    if language_code not in VOICE_CONFIG:
        raise ValueError(f"Language {language_code} not supported")
    return VOICE_CONFIG[language_code]
