"""
Script generator for audio lessons using unified LLM service.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

from zeeguu.core.audio_lessons.script_language_validator import (
    TARGET_LANGUAGE_VOICES,
    find_language_mismatches,
)
from zeeguu.core.audio_lessons.script_parser import join_continuation_lines, parse_script, unknown_speaker_labels
from zeeguu.core.audio_lessons.lesson_script.challenges import challenges
from zeeguu.core.audio_lessons.lesson_script.markers import VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import without_teacher_chevron_spans
from zeeguu.core.audio_lessons.lesson_script.roles import roles_to_voices, voices_to_roles
from zeeguu.core.audio_lessons.lesson_script.voices import other_voice
from zeeguu.core.audio_lessons.words_heard import history_table
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
@dataclass(frozen=True)
class GeneratedScript:
    script: str
    model_name: str
    prompt_version: str
    # For a lesson written in two calls, the GeneratedScript of the call that
    # wrote its dialogue; None otherwise.
    dialogue: Optional["GeneratedScript"] = None
    marked: Optional[str] = None  # an A0 script as the model wrote it, with markers (lesson_script)
    reviewed: tuple = ()  # ids of the earlier lessons' challenges it reviews, in order (lesson_review.py)
    challenges: tuple = ()  # its own challenges, for later lessons to review (lesson_script.challenges)


_PROMPT_VERSION = re.compile(r"-(v\d+)$")


def prompt_version_of(prompt_file: str) -> str:
    """
    'meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v4.txt'
        -> 'meaning_lesson-v4'

    The family and the version, not the whole filename. The 43 characters in
    between name the prompt's strategy, and rewording them is a tidy-up rather
    than a new version — recording them would make a rename look like a version
    bump, and would not fit AIGenerator.prompt_version (VARCHAR(50)) anyway.

    The two dialogue prompts both reduce to 'dialogue_lesson-v2' (and, from
    Nov 2026, 'dialogue_lesson-v3'); which of them ran is recoverable from the
    row's own lesson_type.
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


def language_contract(target_lang_name: str, source_lang_name: str, voices=("Man", "Woman"), chevrons=False,
                      teacher_l2=True) -> str:
    """
    The two-language rule, as a system prompt.

    teacher_l2: the prompt has the Teacher say learned-language words on
    TeacherL2: lines (meaning lessons). The dialogue prompts above A0 have no
    such lines since v3, and are not told about them.

    A lesson script carries two languages at once, and which voice speaks which is
    the whole point of it. Stating that only in the user prompt leaves it competing
    with several hundred lines of formatting instructions: measured on DeepSeek,
    scripts with a non-English teacher held the rule 1 time in 9 that way, and 7
    times in 9 with the rule stated here instead.
    """
    learned_labels = f"'{voices[0]}:', '{voices[1]}:'" + (" and 'TeacherL2:'" if teacher_l2 else "")
    teacher_rule = f"Lines labeled 'Teacher:' are ALWAYS written in {source_lang_name}"
    if chevrons:
        teacher_rule += f", except words in «chevrons», which are {target_lang_name}"
    return (
        f"You write audio lesson scripts for language learners. The learner speaks "
        f"{source_lang_name} natively and is studying {target_lang_name}.\n"
        f"Lines labeled {learned_labels} are ALWAYS written in "
        f"{target_lang_name}. Never in {source_lang_name}.\n"
        f"{teacher_rule}.\n"
        f"Keeping these two languages apart is the entire purpose of the script. A "
        f"script whose {voices[0]}/{voices[1]} lines are in {source_lang_name} is worthless to the "
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


def _labels_note(labels, voice_labels=("Man", "Woman"), chevrons=False, teacher_l2=True) -> str:
    """The rewrite note for lines under labels no voice says, in the labels
    the prompt asked for (an A0 script: Learner and Other)."""
    a, b = voice_labels
    allowed = f"Teacher:, TeacherL2:, {a}: and {b}:" if teacher_l2 and not chevrons else f"Teacher:, {a}: and {b}:"
    return (
        "\n\nYour previous attempt labeled lines with "
        + ", ".join(f"'{label}:'" for label in labels)
        + f". Those lines are never spoken: only the labels {allowed} have a voice. "
        f"Write it again, and label every line of the dialogue {a}: or {b}:. "
        "The characters' names may appear in what they say, never as a label."
    )


def _correction_note(mismatches, target_lang_name, source_lang_name,
                     voice_labels=("Man", "Woman"), chevrons=False, teacher_l2=True) -> str:
    """The rewrite note for lines in the wrong language, in the labels the
    prompt asked for."""
    a, b = voice_labels
    learned = f"The {a}, {b} and TeacherL2 lines" if teacher_l2 and not chevrons else f"The {a} and {b} lines"
    teacher = (
        f"The Teacher lines MUST be in {source_lang_name}, except words in «chevrons»."
        if chevrons
        else f"The Teacher lines MUST be in {source_lang_name}."
    )
    return (
        "\n\nYour previous attempt used the wrong language: "
        f"{describe_mismatches(mismatches)}.\n"
        f"Write it again. {learned} MUST be in {target_lang_name}. {teacher} "
        "Translate: do not leave any line in the language of the previous attempt."
    )


def generate_script_in_languages(
    prompt: str,
    target_language: str,
    source_language: str,
    context: str,
    max_tokens: int = None,
    short_lines: bool = False,
    deepseek_first: bool = False,
    voice_labels=("Man", "Woman"),
    relabel=None,
    chevrons=False,
    teacher_l2=True,
) -> tuple:
    """
    Generate a lesson script and verify it came back in the languages we asked for.

    voice_labels: the labels the prompt asks for on learned-language lines;
    teacher_l2: whether the prompt has TeacherL2: lines (language_contract).
    relabel: turns them into the voices' labels (Man/Woman) before any check
    reads the script. An A0 script is written with Learner/Other
    (lesson_script.roles.roles_to_voices).

    short_lines: an A0 script, made of one- and two-word lines; see
    script_language_validator.MIN_CHARS_TO_JUDGE_SHORT_LINES.
    deepseek_first: ask DeepSeek first and Anthropic only if it fails.

    Retries with an explicit correction when the detected language is wrong, and
    raises if the LLM keeps getting it wrong.
    """
    kwargs = {"max_tokens": max_tokens} if max_tokens else {}
    if deepseek_first:
        kwargs["deepseek_first"] = True
    target_lang_name = Language.LANGUAGE_NAMES.get(target_language, target_language)
    source_lang_name = Language.LANGUAGE_NAMES.get(source_language, source_language)
    kwargs["system"] = language_contract(target_lang_name, source_lang_name, voice_labels, chevrons, teacher_l2)

    attempt_prompt = prompt
    mismatches = []

    for attempt in range(1, LANGUAGE_ATTEMPTS + 1):
        script, model_name = generate_audio_lesson_script(attempt_prompt, **kwargs)
        if relabel:
            script = relabel(script)

        if not _is_a_script(script):
            # Raised, not retried, and the model's own words are carried out with it:
            # they are the finding. Either our data is wrong or the word is one the
            # model won't teach, and both need a person, not another attempt.
            raise NotAScript(
                f"{context}: the model did not write a script. It said: "
                f"{(script or '').strip()[:300]!r}"
            )

        # A slip in the format, not a refusal (see NotAScript): the script was
        # written, with some of its lines under labels no voice says.
        labels = unknown_speaker_labels(script)
        if labels:
            log(
                f"{context} (attempt {attempt}/{LANGUAGE_ATTEMPTS}): lines labeled "
                f"{labels}, which no voice says"
            )
            attempt_prompt = prompt + _labels_note(labels, voice_labels, chevrons, teacher_l2)
            continue

        mismatches = find_language_mismatches(
            # A learned-language word inside a Teacher line of an A0 script
            # («kaffe») is not the Teacher's language: the check must not read
            # it. Only here: elsewhere «» are ordinary quotation marks.
            without_teacher_chevron_spans(script) if chevrons else script,
            target_language, source_language, short_lines=short_lines,
        )
        if not mismatches:
            return script, model_name

        log_mismatches(f"{context} (attempt {attempt}/{LANGUAGE_ATTEMPTS})", mismatches)
        attempt_prompt = prompt + _correction_note(
            mismatches, target_lang_name, source_lang_name, voice_labels, chevrons, teacher_l2
        )

    if labels:
        raise Exception(
            f"Script for {context} labeled lines with {labels} "
            f"{LANGUAGE_ATTEMPTS} times; no voice would say them"
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
    confirmed pair verdict sets; see _meaning_confirmed_wrong). Like NotAScript, the
    model's findings travel with the exception.
    """

    def __init__(self, message, problems, pair_verdict=None):
        super().__init__(message)
        self.problems = problems
        # The pair-only verdict when it found the pair wrong (a
        # ValidationResult, with the correction if it has one)
        self.pair_verdict = pair_verdict

    @property
    def about_the_data(self):
        return self.pair_verdict is not None


def _meaning_confirmed_wrong(lesson):
    """
    A second, pair-only opinion before we act on the script check's word or
    translation complaint: acting marks the meaning INVALID and takes it out of
    study for every learner, and the script check is a lesson reviewer, noisy
    on pairs (2 of the 6 pairs it refused in the 2026-10-18 sample were
    doubtful). This asks the translation validator's own question, in the
    learner's sentence; without a sentence there is nothing to confirm against.
    Any failure to get an answer counts as not confirmed. Returns the verdict
    (a ValidationResult) when it says the pair is wrong, else None.
    """
    from zeeguu.core.audio_lessons.lesson_correctness_check import second_opinion_on_meaning
    from zeeguu.core.llm_services.deepseek_service import DeepSeekService

    if not lesson.context:
        return None
    try:
        verdict = second_opinion_on_meaning(DeepSeekService(), lesson)
    except Exception as e:
        log(f"[lesson check] could not confirm the pair '{lesson.word}': {e}")
        return None
    log(f"[lesson check] pair '{lesson.word}' → '{lesson.translation}': "
        f"{verdict.verdict} ({verdict.reason})")
    # A give-up (a broken sentence, or no meaning that fits) says nothing
    # against the pair: not confirmed
    return None if verdict.is_valid or verdict.gave_up else verdict


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
    pair_verdict, pair_asked = None, False  # asked at most once
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
            if not pair_asked:
                pair_verdict, pair_asked = _meaning_confirmed_wrong(lesson), True
            if pair_verdict:
                break
        # Unconfirmed pair complaints go into the rewrite like any other problem
        attempt_prompt = prompt + _correctness_note(problems)

    raise LessonNotCorrect(
        f"meaning lesson '{origin_word}' → '{translation_word}' did not pass the "
        f"correctness check: {found[:500]}",
        problems,
        pair_verdict=pair_verdict,
    )


def builds_on_history(cefr_level: str) -> bool:
    """
    Whether a situation lesson at this level is written from the learner's own
    history (words_heard), Pimsleur-style, and belongs to them alone. The one
    place this is decided: the generator and the script writer both ask here.
    """
    return cefr_level == "A0"


def word_lesson_level(cefr_level: str) -> str:
    """
    The level a word (meaning) lesson is written at. There is no A0 word lesson:
    A0 is a way of building situation lessons, and meaning lessons are cached and
    shared across users by word, so an "A0" one would be served to everyone.
    """
    return "A1" if cefr_level == "A0" else cefr_level


def generate_dialogue_script(
    origin_language: str,
    translation_language: str,
    suggestion: str,
    lesson_type: str,
    cefr_level: str = "A1",
    past_titles: list = None,
    heard: list = None,
    learner_character: str = None,
    tuning=None,
    lesson_minutes: int = None,
) -> tuple:
    """
    Generate a single flowing dialogue script about a topic or situation.

    At a level that builds_on_history:
    heard: the lessons the learner heard before (words_heard.heard_lessons);
    [] or None when they have heard nothing yet.
    learner_character: "man" or "woman", the character the learner plays.
    tuning: the learner's LessonTuning (lesson_tuning.py); None is the lesson
    as it was before tuning.
    lesson_minutes: the length the learner wants (lesson_tuning.lesson_minutes_for);
    None is the default for a 10-minute daily goal.
    Such a lesson is written in two calls, see _dialogue_for_beginner.

    Returns:
        Tuple of (title, script) — title is a short description of the dialogue
    """
    origin_lang_name = Language.LANGUAGE_NAMES.get(origin_language, origin_language)
    translation_lang_name = Language.LANGUAGE_NAMES.get(translation_language, translation_language)

    # A0 scripts measured 2.3k tokens at 10 minutes and 3.7k at 20 (Danish,
    # 2026-11-20), so a 30-minute one needs ~6k: room above that, since a reply
    # cut off at the limit comes back as if complete (zeeguu/api#863).
    max_tokens = 12000 if builds_on_history(cefr_level) else 8000
    common = dict(
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
        suggestion=suggestion,
    )

    if builds_on_history(cefr_level):
        # One prompt for topics and situations: at A0 a topic is a situation
        # where people talk about it.
        from zeeguu.core.audio_lessons.lesson_tuning import (
            LessonTuning,
            default_lesson_minutes,
            prompt_values,
        )

        prompt_file = A0_LESSON_PROMPT
        heard = heard or []
        tuning = tuning or LessonTuning()
        learner_role = (learner_character or "man").capitalize()
        dialogue = _dialogue_for_beginner(
            origin_language, translation_language, suggestion, heard, learner_role
        )
        values = prompt_values(tuning, lesson_minutes or default_lesson_minutes(10))
        prompt = get_prompt_template(prompt_file).format(
            **common,
            **values,
            history=history_table(heard) or "Nothing yet: this is their first lesson.",
            # The model writes and reads roles, not voices: the Learner and the
            # Other person. Code knows which voice the learner has.
            dialogue=voices_to_roles(dialogue.script, learner_role.lower()),
            learner_gender=learner_role.lower(),
            other_gender=other_voice(learner_role.lower()),
        )
        a0 = dict(
            values=values,
            dialogue=dialogue_lines(dialogue.script),
            heard=heard,
            learner=learner_role.lower(),
        )
    else:
        dialogue = None
        a0 = None
        if lesson_type == "situation":
            prompt_file = SITUATION_LESSON_PROMPT
        else:
            prompt_file = TOPIC_LESSON_PROMPT
        prompt = get_prompt_template(prompt_file).format(**common)

    if past_titles:
        titles_list = "\n".join([f"- {t}" for t in past_titles])
        prompt += f"\n\nIMPORTANT: The following dialogues about this topic already exist. Create a DIFFERENT scenario:\n{titles_list}\n"

    log(f"Generating dialogue script (suggestion: {suggestion}, type: {lesson_type})")

    try:
        title, script, model_name, marked, reviewed = _write_dialogue_lesson(
            prompt,
            a0,
            origin_language=origin_language,
            translation_language=translation_language,
            suggestion=suggestion,
            max_tokens=max_tokens,
            short_lines=builds_on_history(cefr_level),
            marked=prompt_file in MARKED_PROMPTS,
        )
        log(f"Successfully generated dialogue script, title: '{title}'")
        return title, GeneratedScript(
            script, model_name, prompt_version_of(prompt_file), dialogue, marked, reviewed,
            tuple(challenges(marked, a0["learner"])) if marked and a0 else (),  # reviewed by later A0 lessons only
        )

    except Exception as e:
        log(f"Failed to generate dialogue script: {e}")
        raise Exception(f"Failed to generate dialogue script: {str(e)}")


MARKUP_ATTEMPTS = 2

# A pause the model wrote anyway: expand_lines drops it, so the answers are
# counted without it ("[answer] [3 seconds]" is an answer).
_PAUSES = re.compile(r"\s*\[[0-9.]+\s*seconds?\]", re.IGNORECASE)
# A line that only separates sections: "---", "***", "===".
_SEPARATOR = re.compile(r"^\s*(?:[-*_=]\s*){3,}$")


def _tidied(script):
    """
    A marked script above A0, with what v2 scripts were forgiven forgiven here
    too, before expand_lines reads it strictly: section separators dropped,
    bold labels unbolded, a line the model wrapped joined back to its voice
    line (script_parser.join_continuation_lines).
    """
    kept = "\n".join(line for line in script.split("\n") if not _SEPARATOR.match(line))
    return join_continuation_lines(kept)


def _write_dialogue_lesson(prompt, a0, *, origin_language, translation_language, suggestion,
                           max_tokens, short_lines, marked=False):
    """
    (title, script, model, marked, reviewed) from the model; reviewed is the
    ids of the challenges it reviews, in order.

    An A0 script comes back marked (lesson_script): it is expanded here,
    and a review of earlier lessons, chosen by code (lesson_review.py), is put
    before its end to make it as long as the learner asked for. A marker that
    cannot be expanded gets one rewrite, with the reason.

    marked: a lesson above A0 whose prompt is in MARKED_PROMPTS. It is
    tidied (_tidied), then expanded the same way, at shared_lesson_values()
    (the lesson is shared between learners), with no review.
    """
    from zeeguu.core.audio_lessons import lesson_review
    from zeeguu.core.audio_lessons.lesson_script.expand import MarkupError, expand_lines
    from zeeguu.core.audio_lessons.lesson_script.review import review_lines, said_line_count, with_review
    from zeeguu.core.audio_lessons.lesson_tuning import lines_for

    attempt_prompt = prompt
    for attempt in range(1, MARKUP_ATTEMPTS + 1):
        raw, model_name = generate_script_in_languages(
            attempt_prompt,
            target_language=origin_language,
            source_language=translation_language,
            context=f"dialogue lesson '{suggestion}'",
            max_tokens=max_tokens,
            short_lines=short_lines,
            **(
                dict(
                    voice_labels=("Learner", "Other"),
                    relabel=lambda raw: roles_to_voices(raw, a0["learner"]),
                    chevrons=True,
                )
                if a0
                # A marked dialogue prompt above A0 has no TeacherL2: lines (v3)
                else dict(teacher_l2=not marked)
            ),
            # Above A0, DeepSeek writes these as well as Sonnet 5.5 and about 10x
            # cheaper: on 25 prod requests (9 learned, 6 teacher languages) blind
            # A/B judges split evenly and found as many errors in each
            # (zeeguu-experiments audio-lessons/2026-11-18-deepseek-dialogues).
            # A0 lessons and meaning lessons were not part of that comparison.
            deepseek_first=not short_lines,
        )

        # Parse title from first line
        title = None
        script = raw
        lines = raw.strip().split("\n", 1)
        # The title: a first line that is not a voice line or a marker.
        if len(lines) == 2 and not VOICE_LINE.match(lines[0].strip()) and not lines[0].strip().startswith("["):
            title = lines[0].strip().lstrip("#").strip()[:200]
            script = lines[1].strip()

        if a0 is None and not marked:
            return title, script, model_name, None, ()
        try:
            if a0 is None:
                script = _tidied(script)
                answers = len(re.findall(r"\[answer\]\s*$", _PAUSES.sub("", script), re.MULTILINE | re.IGNORECASE))
                if answers < MIN_MARKED_ANSWERS:
                    # An answer without its marker is said once with a second
                    # after it: no time to speak, no repetition. DeepSeek left
                    # the markers out of 14 of 16 lessons in the eval
                    # (zeeguu-experiments audio-lessons/2026-11-27-b1-answer-time).
                    raise MarkupError(
                        f"only {answers} lines end with [answer]: the answer line of every "
                        "challenge ends with [answer]"
                    )
                expanded_lines = expand_lines(script, shared_lesson_values(), chevrons=False)
            else:
                values = a0["values"]
                known = {word for lesson in a0["heard"] for word in lesson.words}
                expanded_lines = expand_lines(script, values, a0["dialogue"], a0["learner"], known)
            expanded = "\n".join(str(line) for line in expanded_lines).strip() + "\n"
        except MarkupError as e:
            log(f"[lesson markup] '{suggestion}' attempt {attempt}/{MARKUP_ATTEMPTS}: {e}")
            if attempt == MARKUP_ATTEMPTS:
                raise
            attempt_prompt = prompt + (
                f"\n\nYour previous attempt broke these rules: {e}. Write it again, "
                "following the rules described above."
            )
            continue

        if a0 is None:
            return title, expanded, model_name, script, ()

        missing = lines_for(values["min_minutes"]) - said_line_count(expanded_lines)
        reviews = lesson_review.choose(a0["heard"], missing, values, a0["learner"])
        full = with_review(expanded, review_lines([challenge for _, challenge in reviews], values))
        reviewed = tuple(challenge_id for challenge_id, _ in reviews)
        return title, full, model_name, script, reviewed


A0_LESSON_PROMPT = "a0_dialogue_lesson--pimsleur_style_situation-v5.txt"

# v3 writes [answer] markers instead of pauses: code gives each challenge the
# time its answer needs (lesson_script.time_to_answer), where v2's fixed
# 5 seconds was too short to repeat a long phrase (a B1 learner, Nov 2026).
# v3 also drops TeacherL2, which v2 allowed but never asked for, and which no
# dialogue in the evals used: it was copied from the meaning lesson prompt.
SITUATION_LESSON_PROMPT = "dialogue_lesson--situation-v3.txt"
TOPIC_LESSON_PROMPT = "dialogue_lesson--topic-v3.txt"
# The lessons above A0 written with markers and expanded by code, like A0's.
MARKED_PROMPTS = {SITUATION_LESSON_PROMPT, TOPIC_LESSON_PROMPT}
# Fewer marked answers than this and the markers were left out: the prompt asks
# for at least 12 challenges.
MIN_MARKED_ANSWERS = 8


def shared_lesson_values():
    """
    The pace of a marked lesson above A0: the default, since such a lesson
    is shared between learners (AudioLessonDialogue.find_unheard) and cannot
    follow one learner's tuning; and 5-10 s to answer (ABOVE_A0_SECONDS).
    """
    from zeeguu.core.audio_lessons.lesson_script.time_to_answer import ABOVE_A0_SECONDS
    from zeeguu.core.audio_lessons.lesson_tuning import DEFAULT_LESSON_MINUTES, LessonTuning, prompt_values

    return {**prompt_values(LessonTuning(), DEFAULT_LESSON_MINUTES), "answer_seconds": ABOVE_A0_SECONDS}


A0_DIALOGUE_PROMPT = "a0_dialogue--natural_exchange-v1.txt"


def dialogue_lines(script):
    """A dialogue as [(voice, text)], voice "man" / "woman"."""
    return tuple(
        (voice, text) for voice, text, _ in parse_script(script or "") if voice in ("man", "woman")
    )


def _dialogue_for_beginner(origin_language, translation_language, suggestion, heard, learner_role):
    """
    The dialogue a beginner's lesson is built around, written on its own.

    Asked for together with the 150 lines of drill around it, the dialogue was
    unnatural in about a third of the lessons (2026-10-18, "at a party: you only
    understand a little"): the model wrote it already thinking in the words it
    had to drill, and kept tacking those on ("Goddag." / "Jeg forstår lidt." /
    "Værsgo."). Asked for alone, 5 of 5 were exchanges as they really happen.
    The lesson is then written around this dialogue and may not change it.
    Returned as a GeneratedScript, so the model that wrote it is recorded too
    (AudioLessonDialogue.dialogue_ai_generator).
    """
    origin_lang_name = Language.LANGUAGE_NAMES.get(origin_language, origin_language)
    known = sorted({word for lesson in heard for word in lesson.words})
    if known:
        known_words = (
            "The learner already knows these words from earlier lessons: "
            + ", ".join(known)
            + ". Use them only where they belong in this situation."
        )
    else:
        known_words = f"This is the learner's first lesson: they know no {origin_lang_name} yet."

    # Without this, a learner whose daily situation is always "at the café" would
    # get the same exchange every day: the same situation and the same known
    # words lead to the same dialogue.
    earlier = [lesson.title for lesson in heard if lesson.title]
    earlier_lessons = (
        "Their earlier lessons were: "
        + "; ".join(earlier[-10:])
        + ". If this situation is one of them, write a different exchange in it."
        if earlier
        else ""
    )

    prompt = get_prompt_template(A0_DIALOGUE_PROMPT).format(
        target_language=origin_lang_name,
        suggestion=suggestion,
        known_words=known_words,
        earlier_lessons=earlier_lessons,
        learner=learner_role.lower(),
    )
    dialogue, model_name = generate_script_in_languages(
        prompt,
        target_language=origin_language,
        source_language=translation_language,
        context=f"A0 dialogue '{suggestion}'",
        max_tokens=500,
        short_lines=True,
    )
    # The lesson around it may not change it, so it is checked here: only the
    # speakers' lines (a preamble like "Here is the dialogue:" is dropped), and
    # 2 to 6 of them. Fewer, or more, means the model did not write what was
    # asked -- possibly cut off -- and the lesson is not built on it.
    lines = []
    for line in dialogue.splitlines():
        # **Woman:** and WOMAN: are the same speaker as Woman:
        speaker_line = re.match(r"^(man|woman)\s*:\s*(\S.*)$", line.replace("*", "").strip(), re.IGNORECASE)
        if speaker_line:
            lines.append(f"{speaker_line.group(1).capitalize()}: {speaker_line.group(2)}")
        elif lines and line.strip():
            # Text after the dialogue has started that is not a speaker's line:
            # a lost turn or a comment. Not dropped silently.
            raise Exception(f"A0 dialogue for '{suggestion}' has a line that is not a speaker's: {line.strip()[:120]!r}")
    if not 2 <= len(lines) <= 6:
        raise Exception(
            f"A0 dialogue for '{suggestion}' has {len(lines)} lines, not 2-6: "
            f"{dialogue.strip()[:300]!r}"
        )
    return GeneratedScript(
        "\n".join(lines),
        model_name,
        prompt_version_of(A0_DIALOGUE_PROMPT),
    )
