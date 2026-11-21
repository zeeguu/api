"""
A0 lesson scripts written with markers, expanded here into the full script.

The model writes each thing once and marks what kind of line it is; this code
adds the repetitions and every pause. So pace and repetition are exactly what
the learner's tuning says (lesson_tuning.prompt_values), rather than what the
model made of "about 5 recalls" and "[4 seconds]", and the model writes about
a quarter fewer lines. Design: docs future-work/a0-lesson-script-functions.md.

    Woman: Kaffe. [drill]                  slow once, then at normal speed
    Teacher: How do you say coffee?        the question: the Teacher line before an
    Woman: En kaffe. [answer]              [answer] gets the time to answer; the
                                           answer is said twice
    Man: Hvad skal det være? [understand]  slow once, then at normal speed
    Woman: Den koster tolv kroner. [cue]   a line the next question answers
    [dialogue]                             this lesson's dialogue

A line with no marker is said once, followed by one second (or by the pause
it carries, when it has one). The expanded script is what is stored and
synthesized: nothing downstream knows about markers.

The review of earlier lessons is not the model's: code chooses it
(lesson_review.py) and places it before the closing dialogue (with_review).
It asks earlier lessons' cards (cards, card_lines): a question in the
learner's own language, time to answer, the answer. A lesson from before
cards is reviewed as its dialogue, answered in the learner's role
(respond_lines).
"""

import re
from dataclasses import dataclass
from typing import Optional

_VOICE_LINE = re.compile(r"^(Teacher|TeacherL2|Man|Woman):\s*(.*)$")
_LINE_MARKER = re.compile(r"\s*\[(drill|answer|understand|cue)\]\s*$", re.IGNORECASE)
_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]\s*$", re.IGNORECASE)
_DIALOGUE = re.compile(r"^\[dialogue\]$", re.IGNORECASE)
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)
# What the model writes when it means "no marker": twice in the eval it wrote
# one, echoing the prompt's wording ("[no marker]", "[plain]"). A plain line.
_PLAIN = re.compile(r"\s*\[(?:plain|no marker|none)\]\s*$", re.IGNORECASE)


class MarkupError(ValueError):
    """The script uses a marker wrongly; the message says how, for a rewrite."""


def _line(voice, text, pause):
    return f"{voice}: {text} [{_seconds(pause)} seconds]"


def _seconds(value):
    return int(value) if float(value).is_integer() else value


def respond_lines(dialogue, learner, values):
    """
    A dialogue for the learner to answer: each line of the other person, then
    the time to answer when the learner speaks next; each line of the learner,
    then the time to repeat it. No straight-through replay: listening again is
    re-exposure, and retrieval is what the review is for.
    dialogue: [(voice, text)] with voice "man" / "woman"; learner: "man" / "woman".
    """
    out = []
    for i, (voice, text) in enumerate(dialogue):
        label = voice.capitalize()
        if voice == learner:
            out.append(_line(label, text, values["repeat_pause"]))
        else:
            learner_next = i + 1 < len(dialogue) and dialogue[i + 1][0] == learner
            out.append(_line(label, text, values["answer_pause"] if learner_next else 1))
    return out


def expand(script, values, dialogue):
    """
    The full script from a marked one.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]. Raises MarkupError on a marker it cannot expand.
    """
    out = []
    problems = []
    for raw in script.split("\n"):
        line = raw.strip()
        if not line:
            out.append("")
            continue

        if _DIALOGUE.match(line):
            out += [_line(voice.capitalize(), text, 1) for voice, text in dialogue]
            continue

        if line.startswith("["):
            if _PAUSE.fullmatch(line):
                out.append(line)
            else:
                problems.append(f"{line!r}: not a marker that stands on its own line")
            continue

        voice_line = _VOICE_LINE.match(line)
        if not voice_line:
            # The title: kept as it is.
            out.append(line)
            continue

        voice, text = voice_line.groups()
        text = _PLAIN.sub("", text)
        marker = _LINE_MARKER.search(text)
        kind = marker.group(1).lower() if marker else None
        text = _LINE_MARKER.sub("", text)
        own_pause = _PAUSE.search(text)
        text = _PAUSE.sub("", text).strip()

        unknown = [
            m for m in _ANY_MARKER.findall(text)
            if m.lower() not in _KNOWN_INLINE and not re.match(r"^[0-9.]+\s*seconds?$", m)
        ]
        if unknown:
            problems.append(f"{line!r}: unknown marker [{unknown[0]}]")
            continue
        text = re.sub(r"\s*\[slow\]", "", text, flags=re.IGNORECASE)

        if kind == "drill":
            out.append(f"{voice}: {text} [slow] [{values['repeat_pause']} seconds]")
            out += [_line(voice, text, values["repeat_pause"])] * values["normal_speed_repeat_count"]
        elif kind == "answer":
            # The question is the Teacher line before the answer: it gets the
            # time to answer. There is no [ask] marker: the model put one in
            # the wrong place in 3 ways (prompt drafts, 20 Nov); now it is
            # refused like any unknown marker, and the script rewritten.
            previous = next((i for i in range(len(out) - 1, -1, -1) if out[i]), None)
            if previous is not None and out[previous].startswith("Teacher:"):
                out[previous] = _PAUSE.sub("", out[previous]) + f" [{values['answer_pause']} seconds]"
            out += [_line(voice, text, values["repeat_pause"])] * 2
        elif kind == "cue":
            out.append(_line(voice, text, 1))
        elif kind == "understand":
            out.append(f"{voice}: {text} [slow] [1 seconds]")
            out.append(_line(voice, text, 1))
        else:
            out.append(_line(voice, text, own_pause.group(1) if own_pause else 1))

    if problems:
        raise MarkupError("; ".join(problems))
    return "\n".join(out).strip() + "\n"


@dataclass(frozen=True)
class Card:
    """A question and its answer from a lesson's marked script, as review material."""

    context: Optional[tuple]  # (voice, text) of the [cue] line the question answers, or None
    prompt: str  # the Teacher's question, in the learner's own language
    answer: tuple  # (voice, text)


@dataclass(frozen=True)
class MarkedLine:
    """One voice line of a marked script."""

    voice: str  # "Teacher", "TeacherL2", "Man" or "Woman"
    text: str  # what is said, without markers
    marker: Optional[str]  # "drill", "answer", "understand", "cue", or None


def marked_lines(marked) -> list:
    """The voice lines of a marked script, in order; the title, blank lines
    and [dialogue] are left out."""
    lines = []
    for raw in (marked or "").split("\n"):
        voice_line = _VOICE_LINE.match(raw.strip())
        if not voice_line:
            continue
        voice, text = voice_line.groups()
        marker = _LINE_MARKER.search(text)
        lines.append(MarkedLine(voice, _clean(text), marker.group(1).lower() if marker else None))
    return lines


def cards(marked):
    """
    The cards of a marked script, in order. A card is an [answer] line, the
    Teacher line right before it (the question), and, when the line before
    the question is marked [cue], that line too (what "Answer her." answers).
    One card per answer: a lesson recalls the same phrase several times, and
    its first question is usually the one that says what it means.

    A second [answer] right after the first (two answers to one question)
    makes no card of its own: the line before it is not a question.
    """
    lines = marked_lines(marked)
    found, answers_seen = [], set()
    for i, line in enumerate(lines):
        if line.marker != "answer":
            continue
        question = lines[i - 1] if i >= 1 else None
        if question is None or question.voice != "Teacher":
            continue
        if line.text.lower() in answers_seen:
            continue
        answers_seen.add(line.text.lower())

        before_question = lines[i - 2] if i >= 2 else None
        cue = before_question if before_question and before_question.marker == "cue" else None

        found.append(Card(
            context=(cue.voice.lower(), cue.text) if cue else None,
            prompt=question.text,
            answer=(line.voice.lower(), line.text),
        ))
    return found


def _clean(text):
    text = re.sub(r"\s*\[[^\]]*\]", "", text)
    return text.strip()


def card_lines(card, values):
    """A card said: its context line, the question, time to answer, the answer twice."""
    out = []
    if card.context:
        out.append(_line(card.context[0].capitalize(), card.context[1], 1))
    out.append(_line("Teacher", card.prompt, values["answer_pause"]))
    out += [_line(card.answer[0].capitalize(), card.answer[1], values["repeat_pause"])] * 2
    return out


def review_lines(items, values):
    """
    The review (lesson_review.ReviewItem, in order): cards as they are; a
    whole dialogue, for a lesson with no cards, opened by its title, said by
    the Teacher (titles are in the learner's own language).
    """
    out = []
    for item in items:
        out.append("")
        if item.card is not None:
            out += card_lines(item.card, values)
        else:
            out.append(_line("Teacher", f"{item.lesson.title}.", 1))
            out += respond_lines(item.lesson.dialogue, item.lesson.learner, values)
    return out


def with_review(expanded, review):
    """
    The expanded script with the review lines put before the closing dialogue:
    before the Teacher's line that introduces it ("Listen again..."), found
    as the last Teacher line. Nothing to put: the script as it was.
    """
    if not review:
        return expanded
    lines = expanded.rstrip("\n").split("\n")
    last_teacher = max((i for i, l in enumerate(lines) if l.startswith("Teacher:")), default=len(lines))
    return "\n".join(lines[:last_teacher] + review + [""] + lines[last_teacher:]) + "\n"


def voice_line_count(lines):
    return sum(1 for line in lines if _VOICE_LINE.match(line.strip()))
