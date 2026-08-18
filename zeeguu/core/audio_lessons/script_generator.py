"""
Script generator for audio lessons using unified LLM service.
"""

import os
from zeeguu.core.audio_lessons.script_language_validator import find_language_mismatches
from zeeguu.core.language.language_check import describe_mismatches, log_mismatches
from zeeguu.core.llm_services import generate_audio_lesson_script
from zeeguu.core.model.language import Language
from zeeguu.logging import log

THREE_WORDS_LESSON = "three_words_lesson"
VALID_LESSON_TYPES = (THREE_WORDS_LESSON, "topic", "situation")

# How many times we ask for the script before giving up. The LLM ignoring the
# "Teacher speaks X, Man/Woman speak Y" instruction is rare but not rare enough:
# a lesson in the wrong language is worse than no lesson, so we retry and then fail.
LANGUAGE_ATTEMPTS = 3


# Load the prompt template
def get_prompt_template(file_name) -> str:
    """Load the prompt template from file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(current_dir, "prompts", file_name)

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def _correction_note(mismatches, target_lang_name, source_lang_name) -> str:
    return (
        "\n\nYour previous attempt used the wrong language: "
        f"{describe_mismatches(mismatches)}.\n"
        f"Write it again. The Man, Woman and TeacherL2 lines MUST be in {target_lang_name}. "
        f"The Teacher lines MUST be in {source_lang_name}. Translate — do not leave any line "
        "in the language of the previous attempt."
    )


def generate_script_in_languages(
    prompt: str,
    target_language: str,
    source_language: str,
    context: str,
    max_tokens: int = None,
) -> str:
    """
    Generate a lesson script and verify it came back in the languages we asked for.

    Retries with an explicit correction when the detected language is wrong, and
    raises if the LLM keeps getting it wrong.
    """
    kwargs = {"max_tokens": max_tokens} if max_tokens else {}
    target_lang_name = Language.LANGUAGE_NAMES.get(target_language, target_language)
    source_lang_name = Language.LANGUAGE_NAMES.get(source_language, source_language)

    attempt_prompt = prompt
    mismatches = []

    for attempt in range(1, LANGUAGE_ATTEMPTS + 1):
        script = generate_audio_lesson_script(attempt_prompt, **kwargs)

        mismatches = find_language_mismatches(script, target_language, source_language)
        if not mismatches:
            return script

        log_mismatches(f"{context} (attempt {attempt}/{LANGUAGE_ATTEMPTS})", mismatches)
        attempt_prompt = prompt + _correction_note(
            mismatches, target_lang_name, source_lang_name
        )

    raise Exception(
        f"Script for {context} came back in the wrong language "
        f"{LANGUAGE_ATTEMPTS} times: {describe_mismatches(mismatches)}"
    )


def generate_lesson_script(
    origin_word: str,
    translation_word: str,
    origin_language: str,
    translation_language: str,
    cefr_level: str = "A1",
    generator_prompt_file="meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v3.txt",
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
        script = generate_script_in_languages(
            prompt,
            target_language=origin_language,
            source_language=translation_language,
            context=f"meaning lesson '{origin_word}'",
        )
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
        raw = generate_script_in_languages(
            prompt,
            target_language=origin_language,
            source_language=translation_language,
            context=f"dialogue lesson '{suggestion}'",
            max_tokens=8000,
        )

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
