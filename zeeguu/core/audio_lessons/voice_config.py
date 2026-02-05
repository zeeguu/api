"""
Voice configuration for audio lessons.
Maps voice names and languages to Google Cloud Text-to-Speech voice IDs.
"""

# Voice mappings for different languages
VOICE_CONFIG = {
    "da-DK": {  # Danish
        "woman": "da-DK-Wavenet-A",
        "man": "da-DK-Wavenet-G",
        "teacher": "da-DK-Wavenet-A",
    },
    "es-ES": {  # Spanish
        "woman": "es-ES-Chirp3-HD-Aoede",
        "man": "es-ES-Chirp3-HD-Algenib",
        "teacher": "es-ES-Chirp3-HD-Aoede",
    },
    "it-IT": {  # Italian
        "woman": "it-IT-Wavenet-A",
        "man": "it-IT-Wavenet-D",
        "teacher": "it-IT-Wavenet-A",
    },
    "pt-PT": {  # Portuguese (European)
        "woman": "pt-PT-Wavenet-E",
        "man": "pt-PT-Wavenet-F",
        "teacher": "pt-PT-Wavenet-E",
    },
    "fr-FR": {  # French (France)
        "woman": "fr-FR-Chirp3-HD-Sulafat",
        "man": "fr-FR-Chirp3-HD-Algenib",
        "teacher": "fr-FR-Chirp3-HD-Sulafat",
    },
    "de-DE": {  # German (Germany)
        "woman": "de-DE-Chirp3-HD-Aoede",
        "man": "de-DE-Chirp3-HD-Enceladus",
        "teacher": "de-DE-Chirp3-HD-Aoede",
        # others good women: de-DE-Chirp3-HD-Gacrux, de-DE-Chirp3-HD-Sulafat
        # others good men: de-DE-Chirp3-HD-Algenib, de-DE-Chirp3-HD-Sadachbia
    },
    "nl-NL": {  # Dutch (Netherlands)
        "woman": "nl-NL-Chirp3-HD-Aoede",
        "man": "nl-NL-Chirp3-HD-Enceladus",  # nl-NL-Chirp3-HD-Algieba
        "teacher": "nl-NL-Chirp3-HD-Aoede",
    },
    "sv-SE": {  # Swedish
        "woman": "sv-SE-Standard-F",
        "man": "sv-SE-Standard-G",
        "teacher": "sv-SE-Standard-F",
    },
    "pl-PL": {  # Polish
        "woman": "pl-PL-Wavenet-F",
        "man": "pl-PL-Wavenet-G",
        "teacher": "pl-PL-Wavenet-F",
    },
    "en-US": {  # English
        "teacher": "en-US-Wavenet-J",
        "man": "en-US-Wavenet-D",
        "woman": "en-US-Wavenet-F",
    },
    "ro-RO": {  # Romanian - using Azure (Google has no Romanian support)
        "woman": "ro-RO-AlinaNeural",
        "man": "ro-RO-EmilNeural",
        "teacher": "ro-RO-AlinaNeural",
        "provider": "azure",
    },
    "el-GR": {  # Greek - using Azure (Google only has female voices)
        "woman": "el-GR-AthinaNeural",
        "man": "el-GR-NestorasNeural",
        "teacher": "el-GR-AthinaNeural",
        "provider": "azure",
    },
    "uk-UA": {  # Ukrainian
        "woman": "uk-UA-Chirp3-HD-Aoede",
        "man": "uk-UA-Chirp3-HD-Enceladus",
        "teacher": "uk-UA-Chirp3-HD-Aoede",
    },
}

# Default silence duration between sentences (in seconds)
DEFAULT_SILENCE_SECONDS = 5.0


def _get_short_to_locale_map() -> dict:
    """Derive short code to locale mapping from VOICE_CONFIG keys."""
    return {locale.split("-")[0]: locale for locale in VOICE_CONFIG.keys()}


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
    short_to_locale = _get_short_to_locale_map()
    if language_code in short_to_locale:
        return short_to_locale[language_code]

    raise ValueError(
        f"Language {language_code} not supported. Available: {list(short_to_locale.keys())}"
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


def is_language_supported_for_audio(language_code: str) -> bool:
    """
    Check if a language is supported for audio lesson generation.

    Args:
        language_code: Short code like 'da', 'pl' or full code like 'da-DK'

    Returns:
        True if the language is supported, False otherwise
    """
    # Handle full locale codes
    if "-" in language_code:
        return language_code in VOICE_CONFIG

    # Handle short codes
    return language_code in _get_short_to_locale_map()


def get_supported_languages() -> list:
    """Get list of supported language codes for audio lessons."""
    return list(_get_short_to_locale_map().keys())
