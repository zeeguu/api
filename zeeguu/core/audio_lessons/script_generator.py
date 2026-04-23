"""
Script generator for audio lessons using unified LLM service.
"""

import os
from zeeguu.core.llm_services import generate_audio_lesson_script
from zeeguu.core.model.language import Language
from zeeguu.logging import log

THREE_WORDS_LESSON = "three_words_lesson"
VALID_LESSON_TYPES = (THREE_WORDS_LESSON, "topic", "situation")


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
    Generate a meaning lesson script for a single word (auto mode only).
    """

    origin_lang_name = Language.LANGUAGE_NAMES.get(origin_language, origin_language)
    translation_lang_name = Language.LANGUAGE_NAMES.get(translation_language, translation_language)

    prompt_template = get_prompt_template(generator_prompt_file)
    prompt = prompt_template.format(
        origin_word=origin_word,
        translation_word=translation_word,
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
    )

    log(f"Generating script for {origin_word} -> {translation_word}")

    try:
        # Use unified LLM service with automatic Anthropic -> DeepSeek fallback
        script = generate_audio_lesson_script(prompt)
        log(f"Successfully generated script for {origin_word}")
        return script

    except Exception as e:
        log(f"Failed to generate script for {origin_word}: {e}")
        raise Exception(f"Failed to generate script: {str(e)}")


def generate_dialogue_script(
    origin_language: str,
    translation_language: str,
    suggestion: str,
    lesson_type: str,
    cefr_level: str = "A1",
    past_titles: list = None,
) -> tuple:
    """
    Generate a single flowing dialogue script about a topic or situation.

    Returns:
        Tuple of (title, script) — title is a short description of the dialogue
    """
    origin_lang_name = Language.LANGUAGE_NAMES.get(origin_language, origin_language)
    translation_lang_name = Language.LANGUAGE_NAMES.get(translation_language, translation_language)

    if lesson_type == "situation":
        prompt_file = "dialogue_lesson--situation-v1.txt"
    else:
        prompt_file = "dialogue_lesson--topic-v1.txt"

    prompt_template = get_prompt_template(prompt_file)
    prompt = prompt_template.format(
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
        suggestion=suggestion,
    )

    if past_titles:
        titles_list = "\n".join([f"- {t}" for t in past_titles])
        prompt += f"\n\nIMPORTANT: The following dialogues about this topic already exist. Create a DIFFERENT scenario:\n{titles_list}\n"

    log(f"Generating dialogue script (suggestion: {suggestion}, type: {lesson_type})")

    try:
        raw = generate_audio_lesson_script(prompt, max_tokens=8000)

        # Parse title from first line
        title = None
        script = raw
        lines = raw.strip().split("\n", 1)
        if len(lines) == 2 and not lines[0].strip().startswith("Teacher:"):
            title = lines[0].strip().lstrip("#").strip()[:200]
            script = lines[1].strip()

        log(f"Successfully generated dialogue script, title: '{title}'")
        return title, script

    except Exception as e:
        log(f"Failed to generate dialogue script: {e}")
        raise Exception(f"Failed to generate dialogue script: {str(e)}")
