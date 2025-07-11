"""
Script generator for audio lessons using Claude API.
"""

import os
from anthropic import Anthropic
from zeeguu.logging import log


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
    }

    origin_lang_name = language_names.get(origin_language, origin_language)
    translation_lang_name = language_names.get(
        translation_language, translation_language
    )

    # Load and format the prompt
    prompt_template = get_prompt_template(generator_prompt_file)
    prompt = prompt_template.format(
        origin_word=origin_word,
        translation_word=translation_word,
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
    )

    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)

    try:
        log(f"Generating script for {origin_word} -> {translation_word}")

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        script = response.content[0].text.strip()

        log(f"Successfully generated script for {origin_word}")
        return script

    except Exception as e:
        raise Exception(f"Failed to generate script: {str(e)}")
