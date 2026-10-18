"""
Asks DeepSeek whether a stored meaning lesson teaches its word correctly.

A meaning lesson is reused for everyone learning that meaning, so one wrong
script keeps being served until it is deprecated. At build time only the
languages are checked (script_language_validator) and a refusal is stopped
(NotAScript); nothing checks that the lines mean what the Teacher says they mean.

The word/translation pair being right is not enough. Lesson 41749 (Danish
"Sådan" → "How", deepseek-chat, meaning_lesson-v4) was built on a pair that is
correct in its headline, "Sådan bruger en ekspert mindre tid på sin telefon",
and then taught "Sådan gør du det?" for "How do you do it?". Sådan means "like
this / that way"; "how" is hvordan. So the check reads the lesson itself.

Used by tools/audit_meaning_lesson_correctness.py. The lessons are plain
LessonToCheck values, so the check needs no database and no app context.
"""

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Optional

from zeeguu.core.audio_lessons.script_parser import join_continuation_lines
from zeeguu.core.model.language import Language

PASS = "pass"
FAIL = "fail"
ERROR = "error"

# What a problem is about, as the prompt names it. "word" and "translation" are
# about our data, not the script: writing the script again cannot fix them.
# "unnatural" is real but minor, and the 2026-10-18 sample showed it is also
# where the checker is least reliable ("des inquiétudes graves" flagged), so it
# never blocks a lesson. A kind we do not know counts as blocking.
KINDS = ("word", "translation", "sense", "mismatch", "grammar", "unnatural", "note")
ABOUT_THE_DATA = ("word", "translation")
MINOR = ("unnatural",)

_PAUSE = re.compile(r"\s*\[[0-9.]+\s*seconds?\]", re.IGNORECASE)


@dataclass
class LessonToCheck:
    id: int
    learned_language: str  # code of the language the word is in
    teacher_language: str  # code of the language the Teacher speaks
    translation_language: str
    word: str
    translation: str
    validated: int  # meaning.validated: 0 never checked, 1 valid, 2 invalid
    context: Optional[str]  # the sentence the word was looked up in
    script: str


LESSON_SYSTEM = (
    "You are a meticulous language teacher reviewing audio lessons before "
    "learners hear them. You reply with a single JSON object and nothing else."
)

LESSON_PROMPT = """An audio lesson teaches the {learned_name} word "{word}" with the meaning "{translation}" ({translation_name}).

{context_paragraph}

The lesson is reused for every learner of this word, so they hear it away from that sentence. A translation that is right in one sentence may not generalize: "{word}" may mean "{translation}" only in that sentence, or only in some constructions. Judge each line by what "{word}" really means in {learned_name}, not by the translation the lesson was built on. For example, if German "Bank" were taught as "bench", a line where "Bank" is a place that keeps money would be wrong, even though "bench" is a correct translation of "Bank".

If Teacher lines state precisely what "{word}" means in this lesson, "{translation}" is only a short gloss of that meaning: judge every line against the stated meaning, and call the translation wrong only if the stated meaning is wrong for the original sentence.

Voices: "Teacher" speaks {teacher_name}. The Teacher introduces the word, adds notes about it, and prompts the learner ("Say, ...", "Ask, ..."). "Man", "Woman" and "TeacherL2" speak {learned_name}. After each Teacher prompt, the {learned_name} line that follows is the answer the learner is expected to say.

The lesson, one numbered line per voice line:
{numbered_script}

Check, and give each problem the kind named here:
1. "word": is "{word}" a real {learned_name} word or phrase, spelled correctly?
2. "translation": is "{translation}" a correct translation of "{word}" in the original sentence?
3. "sense": on every line where "{word}" appears (in any form), is it used in a sense that "{translation}" covers? Flag every line that uses it in a sense the translation does not cover, and every line that uses it where {learned_name} would need a different word.
4. "mismatch": does each Teacher prompt ask for exactly what the {learned_name} answer after it says? Flag a different meaning, tense, person, negation, a question answered with a statement, or content missing or added.
5. "grammar": is every {learned_name} line grammatical? "unnatural": is it something a native speaker would say?
6. "note": is what the Teacher says about the word (other meanings, a more common synonym, how it is used) true?

Do not flag pauses, repetition, difficulty level, the choice of examples, or style preferences. Flag only what would teach the learner something wrong or make them say something wrong. If, thinking about a line, you conclude it is fine after all, leave it out.

Reply with only this JSON object:
{{"verdict": "pass" or "fail", "problems": [{{"line": <line number, or 0 for the lesson as a whole>, "kind": "<word|translation|sense|mismatch|grammar|unnatural|note>", "issue": "<one sentence in English>"}}]}}
The verdict is "fail" when there is at least one problem."""

WITH_CONTEXT = (
    'A learner looked the word up in this {learned_name} sentence, and "{translation}" '
    'was the translation given there:\n"{context}"'
)
WITHOUT_CONTEXT = "The sentence the word was looked up in is not available."

# The translation validator's prompt asks for its fields by name; with
# Anthropic the API enforces the shape, here we have to ask for it.
PAIR_JSON_REMINDER = """

Reply with only a JSON object with exactly these keys: reason, verdict,
corrected_word, corrected_translation, frequency, cefr, phrase_type,
explanation, literal_meaning. Use an empty string for a field that does not apply."""


def checker_id(model: str) -> str:
    """Names the model and the exact prompt text a verdict came from.

    --deprecate acts only on verdicts with the current checker_id; see the
    2026-08-18 note in tools/audit_audio_lesson_script_languages.py for what
    happens when a run acts on a report from a different configuration.
    """
    text = LESSON_SYSTEM + LESSON_PROMPT + WITH_CONTEXT + WITHOUT_CONTEXT
    return f"{model}:{hashlib.sha1(text.encode()).hexdigest()[:8]}"


def numbered_lines(script: str) -> list:
    """The script's voice lines, pauses removed. Line n of the prompt is
    numbered_lines(script)[n - 1], which is how a reported line is resolved."""
    return [
        _PAUSE.sub("", line).strip()
        for line in join_continuation_lines(script or "").split("\n")
        if _PAUSE.sub("", line).strip()
    ]


def lesson_prompt(lesson: LessonToCheck) -> str:
    def name(code):
        return Language.LANGUAGE_NAMES.get(code, code)

    if lesson.context:
        context_paragraph = WITH_CONTEXT.format(
            learned_name=name(lesson.learned_language),
            translation=lesson.translation,
            context=lesson.context.strip(),
        )
    else:
        context_paragraph = WITHOUT_CONTEXT

    lines = numbered_lines(lesson.script)
    return LESSON_PROMPT.format(
        learned_name=name(lesson.learned_language),
        teacher_name=name(lesson.teacher_language),
        translation_name=name(lesson.translation_language),
        word=lesson.word,
        translation=lesson.translation,
        context_paragraph=context_paragraph,
        numbered_script="\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1)),
    )


def json_object(reply: str) -> dict:
    """The JSON object in a reply that may be wrapped in a ```json fence or
    have a sentence before it. Raises ValueError if there is none."""
    start, end = reply.find("{"), reply.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"no JSON object in reply: {reply[:200]!r}")
    parsed = json.loads(reply[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError(f"reply is not a JSON object: {reply[:200]!r}")
    return parsed


def parse_lesson_verdict(reply: str, lines: list) -> tuple:
    """(verdict, problems) from the model's reply. Each problem gets the text
    of the line it points at, so the report can be read without the script.

    A "pass" that lists problems counts as a fail: the prompt defines fail as
    "at least one problem", and the problems are the part we read. Raises
    ValueError when the reply has no usable verdict.
    """
    parsed = json_object(reply)
    verdict = str(parsed.get("verdict", "")).strip().lower()
    if verdict not in (PASS, FAIL):
        raise ValueError(f"no pass/fail verdict in reply: {reply[:200]!r}")

    problems = []
    for problem in parsed.get("problems") or []:
        if not isinstance(problem, dict):
            problem = {"issue": str(problem)}
        line = _line_number(problem.get("line"))
        kind = str(problem.get("kind", "")).strip().lower()
        problems.append(
            {
                "line": line,
                "text": lines[line - 1] if line and 0 < line <= len(lines) else None,
                "kind": kind if kind in KINDS else "other",
                "issue": str(problem.get("issue", "")).strip(),
            }
        )

    if problems:
        verdict = FAIL
    elif verdict == FAIL:
        problems = [{"line": None, "text": None, "kind": "other", "issue": "(the model gave no reason)"}]
    return verdict, problems


def mark_pair_invalid(db_session, meaning_id, problems, user_word_id=None, context=None):
    """The check found the word or its translation wrong: mark the meaning
    INVALID, so the audio word selector stops picking it, and log why in
    validation_log next to the translation validator's own verdicts. Does not
    commit."""
    from zeeguu.core.model.meaning import Meaning
    from zeeguu.core.model.validation_log import ValidationLog

    reason = "[audio lesson check] " + "; ".join(
        p["issue"] for p in problems if p["kind"] in ABOUT_THE_DATA
    )
    meaning = db_session.get(Meaning, meaning_id)
    meaning.validated = Meaning.INVALID
    db_session.add(meaning)
    ValidationLog.log_invalid(
        db_session, meaning=meaning, user_word_id=user_word_id, reason=reason, context=context
    )


def blocking(problems) -> list:
    """The problems a lesson must not be stored or served with."""
    return [p for p in problems if p["kind"] not in MINOR]


def _line_number(value) -> Optional[int]:
    """12, "12", "L12" and "line 12" all mean line 12; anything else, none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def judge_pair(service, lesson: LessonToCheck):
    """The translation validator's verdict on the pair in its sentence, asked
    of DeepSeek. Its parser expects the reply shape it gets from Anthropic."""
    from zeeguu.core.llm_services.prompts.translation_validator import (
        create_combined_validation_prompt,
    )
    from zeeguu.core.llm_services.translation_validator import TranslationValidator

    prompt = create_combined_validation_prompt(
        word=lesson.word,
        translation=lesson.translation,
        context=lesson.context,
        source_lang=Language.LANGUAGE_NAMES.get(lesson.learned_language),
        target_lang=Language.LANGUAGE_NAMES.get(lesson.translation_language),
    )
    reply = json_object(
        service.generate_text(prompt + PAIR_JSON_REMINDER, max_tokens=1000, temperature=0)
    )
    # Without the schema nothing stops "valid", which the parser would read as FIX.
    reply["verdict"] = str(reply.get("verdict", "")).strip().upper()
    if reply["verdict"] not in ("VALID", "FIX"):
        raise ValueError(f"no VALID/FIX verdict in reply: {str(reply)[:200]}")
    return TranslationValidator._parse_response(json.dumps(reply))


def judge_lesson(service, lesson: LessonToCheck) -> tuple:
    """(verdict, problems) for the lesson's script. Raises when the model
    cannot be asked or its reply has no verdict."""
    reply = service.generate_text(
        lesson_prompt(lesson), max_tokens=2000, temperature=0, system=LESSON_SYSTEM
    )
    return parse_lesson_verdict(reply, numbered_lines(lesson.script))


def check(service, lesson: LessonToCheck) -> dict:
    """One report row. A failed call becomes an "error" row, which the next
    run retries."""
    row = {
        "id": lesson.id,
        "language": lesson.learned_language,
        "word": lesson.word,
        "translation": lesson.translation,
        "validated": lesson.validated,
        "context": lesson.context,
        "checker": checker_id(service.model),
    }

    # Only pairs our own validator never passed: a valid pair is still read
    # against the lesson by check 1 of the lesson prompt.
    if lesson.validated != 1 and lesson.context:
        try:
            pair = judge_pair(service, lesson)
            row["pair_verdict"] = "VALID" if pair.is_valid else "FIX"
            row["pair_reason"] = pair.reason
            if not pair.is_valid:
                row["pair_correction"] = (
                    f"{pair.corrected_word or lesson.word} → "
                    f"{pair.corrected_translation or lesson.translation}"
                )
        except Exception as e:
            row["pair_verdict"] = ERROR
            row["pair_reason"] = str(e)[:300]

    try:
        row["verdict"], row["problems"] = judge_lesson(service, lesson)
    except Exception as e:
        row["verdict"], row["problems"] = ERROR, [
            {"line": None, "text": None, "kind": "other", "issue": str(e)[:300]}
        ]
    return row


class _Spacing:
    """At most one request start per `interval` seconds, across threads."""

    def __init__(self, interval):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_start = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = self.next_start - now
            self.next_start = max(now, self.next_start) + self.interval
        if delay > 0:
            time.sleep(delay)


def check_all(service, lessons, report_path, workers=4, interval=0.5, on_row=None):
    """Check the lessons and append one JSON line per lesson to report_path,
    as each finishes, so an interrupted run loses at most the calls in flight."""
    spacing = _Spacing(interval)

    def one(lesson):
        spacing.wait()
        return check(service, lesson)

    with ThreadPoolExecutor(max_workers=workers) as pool, open(report_path, "a") as report:
        futures = [pool.submit(one, lesson) for lesson in lessons]
        for future in as_completed(futures):
            row = future.result()
            report.write(json.dumps(row, ensure_ascii=False) + "\n")
            report.flush()
            if on_row:
                on_row(row)


def read_report(report_path) -> dict:
    """lesson id → the last row for it. Later rows win, so a re-check replaces
    an earlier error."""
    rows = {}
    try:
        with open(report_path) as report:
            for line in report:
                if line.strip():
                    row = json.loads(line)
                    rows[row["id"]] = row
    except FileNotFoundError:
        pass
    return rows


def is_done(row, checker) -> bool:
    """A verdict from the current checker. Errors, and verdicts from another
    model or another prompt text, are checked again."""
    return row is not None and row.get("checker") == checker and row.get("verdict") in (PASS, FAIL)
