"""
Script generator for audio lessons using unified LLM service.
"""

import os
import re
from collections import namedtuple

from zeeguu.core.audio_lessons.script_language_validator import (
    TARGET_LANGUAGE_VOICES,
    find_language_mismatches,
)
from zeeguu.core.audio_lessons.script_parser import parse_script
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

# What produced a script: the model that actually answered (not the one configured,
# which a fallback chain can silently override) and the prompt file that was used.
# Both are known at generation time and unrecoverable afterwards.
GeneratedScript = namedtuple("GeneratedScript", ["script", "model_name", "prompt_version"])


_PROMPT_VERSION = re.compile(r"-(v\d+)$")


def prompt_version_of(prompt_file: str) -> str:
    """
    'meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v4.txt'
        -> 'meaning_lesson-v4'

    The family and the version, not the whole filename. The 43 characters in
    between name the prompt's strategy, and rewording them is a tidy-up rather
    than a new version — recording them would make a rename look like a version
    bump, and would not fit AIGenerator.prompt_version (VARCHAR(50)) anyway.

    The two dialogue prompts both reduce to 'dialogue_lesson-v2'; which of them
    ran is recoverable from the row's own lesson_type.
    """
    stem = os.path.basename(prompt_file).rsplit(".", 1)[0]
    family = stem.split("--")[0]
    version = _PROMPT_VERSION.search(stem)
    return f"{family}-{version.group(1)}" if version else family


# Load the prompt template
def get_prompt_template(file_name) -> str:
    """Load the prompt template from file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(current_dir, "prompts", file_name)

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def language_contract(target_lang_name: str, source_lang_name: str) -> str:
    """
    The two-language rule, as a system prompt.

    A lesson script carries two languages at once, and which voice speaks which is
    the whole point of it. Stating that only in the user prompt leaves it competing
    with several hundred lines of formatting instructions: measured on DeepSeek,
    scripts with a non-English teacher held the rule 1 time in 9 that way, and 7
    times in 9 with the rule stated here instead.
    """
    return (
        f"You write audio lesson scripts for language learners. The learner speaks "
        f"{source_lang_name} natively and is studying {target_lang_name}.\n"
        f"Lines labelled 'Man:', 'Woman:' and 'TeacherL2:' are ALWAYS written in "
        f"{target_lang_name}. Never in {source_lang_name}.\n"
        f"Lines labelled 'Teacher:' are ALWAYS written in {source_lang_name}.\n"
        f"Keeping these two languages apart is the entire purpose of the script. A "
        f"script whose Man/Woman lines are in {source_lang_name} is worthless to the "
        f"learner and must never be produced."
    )


class NotAScript(Exception):
    """
    The model answered with prose instead of a dialogue, and asking again is wrong.

    Every stored instance of this was the model being RIGHT. Twice it reported that
    our own data was wrong ("amenaza means threat, not hot"; "justement does not
    mean van"), and three times it declined a word it should decline — one of them
    CSAM-related. None of that is a formatting slip.

    An earlier version of this retried with "do not explain, apologise, or comment
    on the request — reply with the script only", which is a prompt engineered to
    push a model past a refusal it was correct to make. It ran against
    'Kinderpornographie'. Do not reintroduce it: if a future case turns out to be a
    genuine format failure, narrow the retry to that case specifically, and never
    to a refusal.
    """


def _is_a_script(script: str) -> bool:
    """A script has lines for the voices that speak the language being learned."""
    return any(
        voice in TARGET_LANGUAGE_VOICES for voice, _, _ in parse_script(script or "")
    )


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
) -> tuple:
    """
    Generate a lesson script and verify it came back in the languages we asked for.

    Retries with an explicit correction when the detected language is wrong, and
    raises if the LLM keeps getting it wrong.
    """
    kwargs = {"max_tokens": max_tokens} if max_tokens else {}
    target_lang_name = Language.LANGUAGE_NAMES.get(target_language, target_language)
    source_lang_name = Language.LANGUAGE_NAMES.get(source_language, source_language)
    kwargs["system"] = language_contract(target_lang_name, source_lang_name)

    attempt_prompt = prompt
    mismatches = []

    for attempt in range(1, LANGUAGE_ATTEMPTS + 1):
        script, model_name = generate_audio_lesson_script(attempt_prompt, **kwargs)

        if not _is_a_script(script):
            # Raised, not retried, and the model's own words are carried out with it:
            # they are the finding. Either our data is wrong or the word is one the
            # model won't teach, and both need a person, not another attempt.
            raise NotAScript(
                f"{context}: the model did not write a script. It said: "
                f"{(script or '').strip()[:300]!r}"
            )

        mismatches = find_language_mismatches(script, target_language, source_language)
        if not mismatches:
            return script, model_name

        log_mismatches(f"{context} (attempt {attempt}/{LANGUAGE_ATTEMPTS})", mismatches)
        attempt_prompt = prompt + _correction_note(
            mismatches, target_lang_name, source_lang_name
        )

    raise Exception(
        f"Script for {context} came back in the wrong language "
        f"{LANGUAGE_ATTEMPTS} times: {describe_mismatches(mismatches)}"
    )


# Script-correctness attempts: the first script, and one rewrite told what the
# check found. On 2026-10-18 a DeepSeek check of 200 stored lessons failed 70% of
# those built on pairs our validator passed (lesson 41749 taught Danish "Sådan
# gør du det?" for "How do you do it?"); the rewrite is cheaper than a learner
# repeating a wrong sentence for weeks.
CORRECTNESS_ATTEMPTS = 2

# v6 has the Teacher say exactly what the word means in this lesson and name its
# other meanings. "How" for Sådan was right in its headline ("this is how"), and
# both the generator and the check read the bare gloss as the question word;
# saying the meaning out loud fixed both (2026-10-18).
MEANING_LESSON_PROMPT = "meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v6.txt"
MEANING_LESSON_PROMPT_VERSION = prompt_version_of(MEANING_LESSON_PROMPT)


class LessonNotCorrect(Exception):
    """
    The script still teaches the word wrong after a rewrite, or the
    word/translation pair itself is wrong (`about_the_data`, which only a
    confirmed pair verdict sets; see _pair_is_wrong). Like NotAScript, the
    model's findings travel with the exception.
    """

    def __init__(self, message, problems, about_the_data=False):
        super().__init__(message)
        self.problems = problems
        self.about_the_data = about_the_data


def _pair_is_wrong(lesson) -> bool:
    """
    A second, pair-only opinion before we act on the script check's word or
    translation complaint: acting marks the meaning INVALID and takes it out of
    study for every learner, and the script check is a lesson reviewer, noisy
    on pairs (2 of the 6 pairs it refused in the 2026-10-18 sample were
    doubtful). This asks the translation validator's own question, in the
    learner's sentence; without a sentence there is nothing to confirm against.
    Any failure to get an answer counts as not confirmed.
    """
    from zeeguu.core.audio_lessons.lesson_correctness_check import judge_pair
    from zeeguu.core.llm_services.deepseek_service import DeepSeekService

    if not lesson.context:
        return False
    try:
        verdict = judge_pair(DeepSeekService(), lesson)
    except Exception as e:
        log(f"[lesson check] could not confirm the pair '{lesson.word}': {e}")
        return False
    log(f"[lesson check] pair '{lesson.word}' → '{lesson.translation}': "
        f"{'VALID' if verdict.is_valid else 'FIX'} ({verdict.reason})")
    return not verdict.is_valid


def _context_paragraph(origin_word, translation_word, context):
    if context:
        return (
            f'The learner met "{origin_word}" in this sentence, where it was translated '
            f'as "{translation_word}":\n"{context.strip()}"'
        )
    return (
        f'The sentence where the learner met "{origin_word}" is not available: use it '
        f'only in the sense that "{translation_word}" translates.'
    )


def _correctness_note(problems) -> str:
    listed = "\n".join(
        f"- {p['text'] or 'the script as a whole'}: {p['issue']}" for p in problems
    )
    return (
        "\n\nA reviewer found these problems in your previous script:\n"
        f"{listed}\nWrite the whole script again without them."
    )


def _blocking_problems(lesson):
    """The problems that keep this script from being stored, or [] when the
    check could not be done. The check failing open is deliberate: a learner
    waits on this, and tools/audit_meaning_lesson_correctness.py --quiet runs
    nightly over whatever got through."""
    from zeeguu.core.audio_lessons.lesson_correctness_check import blocking, judge_lesson
    from zeeguu.core.llm_services.deepseek_service import DeepSeekService

    try:
        _, problems = judge_lesson(DeepSeekService(), lesson)
    except Exception as e:
        log(f"[lesson check] could not check '{lesson.word}', storing unchecked: {e}")
        import sentry_sdk

        sentry_sdk.capture_exception(e)
        return []
    return blocking(problems)


def generate_lesson_script(
    origin_word: str,
    translation_word: str,
    origin_language: str,
    translation_language: str,
    cefr_level: str = "A1",
    context: str = None,
    generator_prompt_file=MEANING_LESSON_PROMPT,
) -> GeneratedScript:
    """
    Generate a meaning lesson script for a single word (auto mode only).

    `context` is the sentence the learner looked the word up in. The translation
    was chosen for that sentence, and without it the model guesses the sense
    from the translation alone ("Sådan" = "How" became the question word).
    """
    from zeeguu.core.audio_lessons.lesson_correctness_check import (
        ABOUT_THE_DATA,
        LessonToCheck,
    )

    origin_lang_name = Language.LANGUAGE_NAMES.get(origin_language, origin_language)
    translation_lang_name = Language.LANGUAGE_NAMES.get(translation_language, translation_language)

    prompt_template = get_prompt_template(generator_prompt_file)
    prompt = prompt_template.format(
        origin_word=origin_word,
        translation_word=translation_word,
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
        context_paragraph=_context_paragraph(origin_word, translation_word, context),
    )

    log(f"Generating script for {origin_word} -> {translation_word}")

    attempt_prompt = prompt
    pair_is_wrong = None  # asked at most once
    for attempt in range(1, CORRECTNESS_ATTEMPTS + 1):
        try:
            # Use unified LLM service with automatic Anthropic -> DeepSeek fallback
            script, model_name = generate_script_in_languages(
                attempt_prompt,
                target_language=origin_language,
                source_language=translation_language,
                context=f"meaning lesson '{origin_word}'",
            )
        except NotAScript:
            # Kept as itself: the caller records it and leaves the word out
            raise
        except Exception as e:
            log(f"Failed to generate script for {origin_word}: {e}")
            raise Exception(f"Failed to generate script: {str(e)}")

        lesson = LessonToCheck(
            id=None,
            learned_language=origin_language,
            teacher_language=translation_language,
            translation_language=translation_language,
            word=origin_word,
            translation=translation_word,
            validated=None,
            context=context,
            script=script,
        )
        problems = _blocking_problems(lesson)
        if not problems:
            log(f"Successfully generated script for {origin_word}")
            return GeneratedScript(script, model_name, prompt_version_of(generator_prompt_file))

        found = "; ".join(f"[{p['kind']}] {p['text'] or ''} {p['issue']}" for p in problems)
        log(f"[lesson check] '{origin_word}' attempt {attempt}/{CORRECTNESS_ATTEMPTS}: {found}")
        if any(p["kind"] in ABOUT_THE_DATA for p in problems):
            if pair_is_wrong is None:
                pair_is_wrong = _pair_is_wrong(lesson)
            if pair_is_wrong:
                break
        # Unconfirmed pair complaints go into the rewrite like any other problem
        attempt_prompt = prompt + _correctness_note(problems)

    raise LessonNotCorrect(
        f"meaning lesson '{origin_word}' → '{translation_word}' did not pass the "
        f"correctness check: {found[:500]}",
        problems,
        about_the_data=bool(pair_is_wrong),
    )


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
        prompt_file = "dialogue_lesson--situation-v2.txt"
    else:
        prompt_file = "dialogue_lesson--topic-v2.txt"

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
        raw, model_name = generate_script_in_languages(
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
        return title, GeneratedScript(script, model_name, prompt_version_of(prompt_file))

    except Exception as e:
        log(f"Failed to generate dialogue script: {e}")
        raise Exception(f"Failed to generate dialogue script: {str(e)}")
