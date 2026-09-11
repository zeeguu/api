"""
Voice configuration for audio lessons.
Maps voice names and languages to Google Cloud Text-to-Speech voice IDs.
"""

# Voice mappings for different languages
VOICE_CONFIG = {
    "da-DK": {  # Danish
        "woman": "da-DK-Chirp3-HD-Aoede",
        "man": "da-DK-Chirp3-HD-Enceladus",
        "teacher": "da-DK-Chirp3-HD-Sulafat",
    },
    "es-ES": {  # Spanish
        "woman": "es-ES-Chirp3-HD-Aoede",
        "man": "es-ES-Chirp3-HD-Algenib",
        "teacher": "es-ES-Chirp3-HD-Sulafat",
    },
    "it-IT": {  # Italian
        "woman": "it-IT-Chirp3-HD-Aoede",
        "man": "it-IT-Chirp3-HD-Enceladus",
        "teacher": "it-IT-Chirp3-HD-Sulafat",
    },
    "pt-PT": {  # Portuguese (European) - no Chirp3-HD available
        "woman": "pt-PT-Wavenet-E",
        "man": "pt-PT-Wavenet-F",
        "teacher": "pt-PT-Standard-E",  # Different voice type for distinction
    },
    "pt-BR": {  # Portuguese (Brazilian) - the one variety of the two that has Chirp3-HD
        "woman": "pt-BR-Chirp3-HD-Aoede",
        "man": "pt-BR-Chirp3-HD-Enceladus",
        "teacher": "pt-BR-Chirp3-HD-Sulafat",
    },
    "fr-FR": {  # French (France)
        "woman": "fr-FR-Chirp3-HD-Aoede",
        "man": "fr-FR-Chirp3-HD-Algenib",
        "teacher": "fr-FR-Chirp3-HD-Sulafat",
    },
    "de-DE": {  # German (Germany)
        "woman": "de-DE-Chirp3-HD-Aoede",
        "man": "de-DE-Chirp3-HD-Enceladus",
        "teacher": "de-DE-Chirp3-HD-Sulafat",
    },
    "nl-NL": {  # Dutch (Netherlands)
        "woman": "nl-NL-Chirp3-HD-Aoede",
        "man": "nl-NL-Chirp3-HD-Enceladus",
        "teacher": "nl-NL-Chirp3-HD-Sulafat",
    },
    "nl-BE": {  # Dutch (Belgium) - Flemish
        "woman": "nl-BE-Chirp3-HD-Aoede",
        "man": "nl-BE-Chirp3-HD-Enceladus",
        "teacher": "nl-BE-Chirp3-HD-Sulafat",
    },
    "sv-SE": {  # Swedish
        "woman": "sv-SE-Chirp3-HD-Aoede",
        "man": "sv-SE-Chirp3-HD-Enceladus",
        "teacher": "sv-SE-Chirp3-HD-Sulafat",
    },
    "pl-PL": {  # Polish
        "woman": "pl-PL-Chirp3-HD-Aoede",
        "man": "pl-PL-Chirp3-HD-Enceladus",
        "teacher": "pl-PL-Chirp3-HD-Sulafat",
    },
    "en-US": {  # English
        "woman": "en-US-Chirp3-HD-Aoede",
        "man": "en-US-Chirp3-HD-Enceladus",
        "teacher": "en-US-Chirp3-HD-Sulafat",
    },
    "ro-RO": {  # Romanian
        "woman": "ro-RO-Chirp3-HD-Aoede",
        "man": "ro-RO-Chirp3-HD-Enceladus",
        "teacher": "ro-RO-Chirp3-HD-Sulafat",
    },
    "el-GR": {  # Greek
        "woman": "el-GR-Chirp3-HD-Aoede",
        "man": "el-GR-Chirp3-HD-Enceladus",
        "teacher": "el-GR-Chirp3-HD-Sulafat",
    },
    "uk-UA": {  # Ukrainian
        "woman": "uk-UA-Chirp3-HD-Aoede",
        "man": "uk-UA-Chirp3-HD-Enceladus",
        "teacher": "uk-UA-Chirp3-HD-Sulafat",
    },
}

# Default silence duration between sentences (in seconds)
DEFAULT_SILENCE_SECONDS = 5.0

# Which locale a language is read in when the learner has asked for no particular
# variety.
#
# This used to be derived by splitting the VOICE_CONFIG keys on "-", which works
# only while every language has exactly one locale. With nl-BE sitting beside
# nl-NL, both halves derive to "nl" and dict order silently decides which accent
# every Dutch learner hears. The default is a decision -- Zeeguu has served
# Netherlands Dutch and European Portuguese since before varieties existed -- so
# it is written down rather than inferred.
DEFAULT_LOCALE = {
    "da": "da-DK",
    "es": "es-ES",
    "it": "it-IT",
    "pt": "pt-PT",
    "fr": "fr-FR",
    "de": "de-DE",
    "nl": "nl-NL",
    "sv": "sv-SE",
    "pl": "pl-PL",
    "en": "en-US",
    "ro": "ro-RO",
    "el": "el-GR",
    "uk": "uk-UA",
}


def _locale_of(language_code: str, country: str) -> str:
    """The VOICE_CONFIG key for a (language, country) pair, whether or not it exists."""
    return f"{language_code}-{country}"


def has_voice(language_code: str, country: str) -> bool:
    """Whether this variety has a voice of its own. Belgian French does not."""
    return _locale_of(language_code, country) in VOICE_CONFIG


def locale_for(language_code: str, variety: str = None) -> str:
    """
    The locale to synthesize in: 'nl-BE' for a Flemish learner, 'nl-NL' for one
    who asked for nothing.

    A variety with no voice of its own falls back to the language's default
    rather than raising. That is not a soft failure to tidy up later: Belgian
    French has no Google voice at all, so a Walloon learner's only alternatives
    are the French of France or silence.
    """
    # Already a full locale (callers pass 'en-US' for the teacher voice).
    if "-" in language_code:
        return language_code

    if language_code not in DEFAULT_LOCALE:
        raise ValueError(
            f"Language {language_code} not supported. Available: {list(DEFAULT_LOCALE.keys())}"
        )

    if variety and has_voice(language_code, variety):
        return _locale_of(language_code, variety)

    return DEFAULT_LOCALE[language_code]


def countries_with_voices(language_code: str) -> tuple:
    """
    The varieties of this language a learner can actually be read in -- the
    options a voice control should offer.

    Derived from what VOICE_CONFIG holds rather than from the catalogue, so the
    control cannot offer an accent nobody can be read in. Fewer than two and it
    offers nothing: a control with a single option asks the learner to make a
    choice that has already been made for them, which is worse than not asking.
    """
    from zeeguu.core.language.varieties import varieties_for

    available = tuple(
        country for country in varieties_for(language_code) if has_voice(language_code, country)
    )
    return available if len(available) > 1 else ()


def voice_catalogue() -> dict:
    """
    The voice varieties, shaped for the client that renders the voice control:
    {"nl": [{"country": "NL", "name": "Dutch from the Netherlands"}, ...]}

    Deliberately not varieties.catalogue(): that one answers "news from where?",
    where "Everywhere" is a coherent answer and French offers Belgium. This one
    answers "read to me in which accent?", where nobody speaks in no particular
    accent and Belgian French has no voice to offer.
    """
    from zeeguu.core.language.varieties import variety_name

    return {
        language_code: [
            dict(country=country, name=variety_name(language_code, country))
            for country in countries_with_voices(language_code)
        ]
        for language_code in DEFAULT_LOCALE
        if countries_with_voices(language_code)
    }


def normalize_language_code(language_code: str, variety: str = None) -> str:
    """
    Convert short language codes to full locale codes.

    Args:
        language_code: Short code like 'it', 'da' or full code like 'it-IT'
        variety: Optional ISO 3166-1 alpha-2 country of the learner's variety

    Returns:
        Full locale code like 'it-IT', 'da-DK'
    """
    return locale_for(language_code, variety)


def get_voice_id(language_code: str, voice_name: str, variety: str = None) -> str:
    """
    Get the Google Cloud TTS voice ID for a given language and voice name.

    Args:
        language_code: Language code like 'da', 'it' or 'da-DK', 'it-IT', etc.
        voice_name: Voice name like 'man', 'woman', 'teacher'
        variety: Optional ISO 3166-1 alpha-2 country of the learner's variety

    Returns:
        Google Cloud TTS voice ID

    Raises:
        ValueError: If language or voice not found in configuration
    """
    # Normalize the language code
    full_language_code = locale_for(language_code, variety)

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
    return language_code in DEFAULT_LOCALE


def get_supported_languages() -> list:
    """Get list of supported language codes for audio lessons."""
    return list(DEFAULT_LOCALE.keys())
