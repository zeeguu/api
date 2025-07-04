"""
Script generator for audio lessons using Claude API.
"""

import os
import json
import requests
from typing import Optional
from zeeguu.logging import log


# Load the prompt template
def get_prompt_template() -> str:
    """Load the prompt template from file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(current_dir, "prompts", "lesson_generation_prompt.txt")

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def generate_lesson_script(
    origin_word: str,
    translation_word: str,
    origin_language: str,
    translation_language: str,
    cefr_level: str = "A1",
) -> str:
    """
    Generate a lesson script using Claude API.

    Args:
        origin_word: The word being learned
        translation_word: The translation
        origin_language: Language code of the word being learned (e.g., 'da')
        translation_language: Language code of the translation (e.g., 'en')
        cefr_level: Cefr level of the word being learned

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
    prompt_template = get_prompt_template()
    prompt = prompt_template.format(
        origin_word=origin_word,
        translation_word=translation_word,
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
    )

    # Prepare the API request
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY environment variable not set")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    data = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        log(f"Generating script for {origin_word} -> {translation_word}")

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=30,
        )

        if response.status_code != 200:
            raise Exception(
                f"Claude API error: {response.status_code} - {response.text}"
            )

        result = response.json()

        if "content" not in result or not result["content"]:
            raise Exception("No content in Claude API response")

        script = result["content"][0]["text"].strip()

        log(f"Successfully generated script for {origin_word}")
        return script

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to call Claude API: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse Claude API response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error generating script: {str(e)}")
