"""
Script generator for audio lessons using unified LLM service.
"""

import os
from zeeguu.core.llm_services import generate_audio_lesson_script
from zeeguu.logging import log

VALID_SUGGESTION_TYPES = ("topic", "situation")


# Load the prompt template
def get_prompt_template(file_name) -> str:
    """Load the prompt template from file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(current_dir, "prompts", file_name)

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def generate_lesson_script(
    origin_word: str,
    translation_word: str,
    origin_language: str,
    translation_language: str,
    cefr_level: str = "A1",
    generator_prompt_file="meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v2.txt",
    suggestion: str = None,
    suggestion_type: str = None,
) -> str:
    """
    Generate a lesson script using Claude API.

    Args:
        origin_word: The word being learned
        translation_word: The translation
        origin_language: Language code of the word being learned (e.g., 'da')
        translation_language: Language code of the translation (e.g., 'en')
        cefr_level: Cefr level of the word being learned
        generator_prompt_file: full filename
        suggestion: Optional short topic hint for the LLM
        suggestion_type: Optional type ("topic" or "situation")

    Returns:
        Generated script text

    Raises:
        Exception: If API call fails or returns unexpected response
    """

    # Get language names for the prompt
    language_names = {
        "da": "Danish",
        "es": "Spanish",
        "en": "English",
        "de": "German",
        "fr": "French",
        "ro": "Romanian",
        "el": "Greek",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
        "sv": "Swedish",
        "pl": "Polish",
        "uk": "Ukrainian",
    }

    origin_lang_name = language_names.get(origin_language, origin_language)
    translation_lang_name = language_names.get(
        translation_language, translation_language
    )

    # Select template based on suggestion type
    if suggestion and suggestion_type == "situation":
        prompt_file = "meaning_lesson--situation-v1.txt"
    elif suggestion and suggestion_type == "topic":
        prompt_file = "meaning_lesson--topic-v1.txt"
    else:
        prompt_file = generator_prompt_file

    prompt_template = get_prompt_template(prompt_file)
    prompt = prompt_template.format(
        origin_word=origin_word,
        translation_word=translation_word,
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
        suggestion=suggestion or "",
    )

    log(f"Generating script for {origin_word} -> {translation_word} (topic: {suggestion}, type: {suggestion_type})")

    try:
        # Use unified LLM service with automatic Anthropic -> DeepSeek fallback
        script = generate_audio_lesson_script(prompt)
        log(f"Successfully generated script for {origin_word}")
        return script

    except Exception as e:
        log(f"Failed to generate script for {origin_word}: {e}")
        raise Exception(f"Failed to generate script: {str(e)}")


def generate_dialogue_script(
    words: list,
    origin_language: str,
    translation_language: str,
    suggestion: str,
    suggestion_type: str,
    cefr_level: str = "A1",
) -> str:
    """
    Generate a single flowing dialogue script that incorporates multiple words.

    Args:
        words: List of (origin_word, translation_word) tuples
        origin_language: Language code of the words being learned (e.g., 'da')
        translation_language: Language code of the translations (e.g., 'en')
        suggestion: The topic or situation for the dialogue
        suggestion_type: "topic" or "situation"
        cefr_level: CEFR level of the learner

    Returns:
        Generated script text
    """
    language_names = {
        "da": "Danish",
        "es": "Spanish",
        "en": "English",
        "de": "German",
        "fr": "French",
        "ro": "Romanian",
        "el": "Greek",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
        "sv": "Swedish",
        "pl": "Polish",
        "uk": "Ukrainian",
    }

    origin_lang_name = language_names.get(origin_language, origin_language)
    translation_lang_name = language_names.get(
        translation_language, translation_language
    )

    # Build the words block for the prompt
    words_block = "\n".join(
        [f'- "{origin}" meaning "{translation}"' for origin, translation in words]
    )

    # Select template
    if suggestion_type == "situation":
        prompt_file = "dialogue_lesson--situation-v1.txt"
    else:
        prompt_file = "dialogue_lesson--topic-v1.txt"

    prompt_template = get_prompt_template(prompt_file)
    prompt = prompt_template.format(
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
        suggestion=suggestion,
        words_block=words_block,
    )

    word_names = ", ".join([w[0] for w in words])
    log(f"Generating dialogue script for [{word_names}] (suggestion: {suggestion}, type: {suggestion_type})")

    try:
        script = generate_audio_lesson_script(prompt, max_tokens=4000)
        log(f"Successfully generated dialogue script for [{word_names}]")
        return script

    except Exception as e:
        log(f"Failed to generate dialogue script: {e}")
        raise Exception(f"Failed to generate dialogue script: {str(e)}")
