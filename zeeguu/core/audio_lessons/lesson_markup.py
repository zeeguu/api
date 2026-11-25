"""
A0 lesson scripts written with markers, expanded here into the full script.

The model writes each thing once and marks what kind of line it is; this code
adds the repetitions and every pause. So pace and repetition are exactly what
the learner's tuning says (lesson_tuning.prompt_values), rather than what the
model made of "about 5 recalls" and "[4 seconds]", and the model writes about
a quarter fewer lines. Design: docs future-work/a0-lesson-script-functions.md.

    The model writes with roles, not voices: "Learner:" and "Other:". Code
    knows which voice (Man or Woman) the learner has, and relabels the lines
    (roles_to_voices) before anything else reads them. Teacher lines are in
    the learner's own language and carry no marker. The learned language is
    marked by what the learner does with it:

    Learner: Kaffe. [drill]                  a word to SAY: slow once, then at
                                             normal speed, with time to repeat it
    Other: Hvad skal det være? [understand]  a line only to UNDERSTAND: slow
                                             once, then at normal speed
    Teacher: How do you say coffee?          a QUESTION: the line right before
    Learner: En kaffe. [answer]              an [answer] gets the time to answer;
                                             the answer is said twice

    An EXCHANGE: the Teacher sets it up, the Other person speaks, and the
    learner replies to them, as in a real conversation:

    Teacher: The shopkeeper tells you the price. Say okay, and ask for a ticket.
    Other: Den koster tolv kroner.           the line the learner answers
    Learner: Okay. En billet, tak. [answer]

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
_LINE_MARKER = re.compile(r"\s*\[(drill|answer|understand)\]\s*$", re.IGNORECASE)
_ROLE_LABEL = re.compile(r"^(\s*)\**\s*(Learner|Other)\s*\**\s*:\s*\**\s*", re.IGNORECASE)
_VOICE_LABEL = re.compile(r"^(\s*)(Man|Woman)\s*:", re.IGNORECASE)


def other_voice(learner):
    """The other person's voice: "woman" for a learner who is "man", and the other way round."""
    return "woman" if learner == "man" else "man"


def roles_to_voices(script, learner):
    """The script with "Learner:" and "Other:" relabeled as the voices they are."""
    voices = {"learner": learner.capitalize(), "other": other_voice(learner).capitalize()}
    return "\n".join(
        _ROLE_LABEL.sub(lambda m: f"{m.group(1)}{voices[m.group(2).lower()]}: ", line)
        for line in (script or "").split("\n")
    )


def voices_to_roles(script, learner):
    """A dialogue with its Man/Woman lines relabeled "Learner:" and "Other:", for the prompt."""
    def role(m):
        return f"{m.group(1)}{'Learner' if m.group(2).lower() == learner else 'Other'}:"
    return "\n".join(_VOICE_LABEL.sub(role, line) for line in (script or "").split("\n"))
_PAUSE = re.compile(r"\s*\[([0-9.]+)\s*seconds?\]\s*$", re.IGNORECASE)
_DIALOGUE = re.compile(r"^\[dialogue\]$", re.IGNORECASE)
_ANY_MARKER = re.compile(r"\[([a-z][a-z ]*\d*)\]", re.IGNORECASE)
_KNOWN_INLINE = ("slow",)
# What the model writes when it means "no marker": twice in the eval it wrote
# one, echoing the prompt's wording ("[no marker]", "[plain]"). A plain line.
_PLAIN = re.compile(r"\s*\[(?:plain|no marker|none)\]\s*$", re.IGNORECASE)


# The time to answer grows with the answer: a beginner recalls each word and
# then says it slowly, so every word adds time, on top of a short start. The
# learner's pace scales all of it (the answer pause, 3-7 s, against its
# default of 5). At the default pace: "Hej." 3 s, "Undskyld, hvad koster en
# billet?" 8 s. Before, every answer had the same 5 s, and a learner asked
# for the time to follow the answer's length (Nov 2026). Estimates, not
# measured: listen to lessons, or time a few learners, before trusting them.
SECONDS_TO_START = 2
SECONDS_PER_WORD = 1.2
DEFAULT_ANSWER_PAUSE = 5
MIN_SECONDS, MAX_SECONDS = 2, 15
_ANSWER_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def time_to_answer(answer, values):
    """Seconds of silence after a question whose answer is `answer`."""
    words = len(_ANSWER_WORD.findall(answer))
    pace = values["answer_pause"] / DEFAULT_ANSWER_PAUSE
    seconds = round(pace * (SECONDS_TO_START + SECONDS_PER_WORD * words))
    return max(MIN_SECONDS, min(MAX_SECONDS, seconds))


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
            pause = time_to_answer(dialogue[i + 1][1], values) if learner_next else 1
            out.append(_line(label, text, pause))
    return out


def expand(script, values, dialogue, learner):
    """
    The full script from a marked one, its lines already labeled with voices.

    values: lesson_tuning.prompt_values; dialogue: this lesson's dialogue as
    [(voice, text)]; learner: the learner's voice, "man" or "woman".
    Raises MarkupError on a marker it cannot expand.
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
            # The line right before the answer is what the learner answers: a
            # Teacher question, or the Other person's line in an exchange. It
            # gets the time to answer. Not the learner's own line before it
            # (two answers in a row): that one already has its pause.
            previous = next((i for i in range(len(out) - 1, -1, -1) if out[i]), None)
            if previous is not None and not out[previous].startswith(f"{learner.capitalize()}:"):
                out[previous] = _PAUSE.sub("", out[previous]) + f" [{time_to_answer(text, values)} seconds]"
            out += [_line(voice, text, values["repeat_pause"])] * 2
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
    """
    One thing the learner answered in a lesson, kept for review: a QUESTION
    (the Teacher asks) or an EXCHANGE (the Other person speaks, after the
    Teacher's setup).
    """

    setup: Optional[str]  # the Teacher's setup of an exchange, in the learner's language; None for a question
    prompt: tuple  # (voice, text) of the line the learner answers: "teacher", or the Other person's voice
    answer: tuple  # (voice, text): the learner's answer

    @property
    def kind(self):
        return "question" if self.prompt[0] in ("teacher", "teacherl2") else "exchange"


@dataclass(frozen=True)
class MarkedLine:
    """One voice line of a marked script."""

    voice: str  # "Teacher", "TeacherL2", "Man" or "Woman"
    text: str  # what is said, without markers
    marker: Optional[str]  # "drill", "answer", "understand", or None


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


def cards(marked, learner):
    """
    The cards of a marked script (with voices), in order. A card is an [answer]
    by the learner and the line right before it, which the learner answers:
    a Teacher question, or the Other person's line in an exchange, then with
    the Teacher's setup before it when there is one. One card per answer: a
    lesson recalls the same phrase several times, and its first question is
    usually the one that says what it means.

    A second [answer] right after the first (two answers to one question)
    makes no card of its own: the line before it is the learner's.
    """
    lines = marked_lines(marked)
    found, answers_seen = [], set()
    for i, line in enumerate(lines):
        if line.marker != "answer" or line.voice.lower() != learner:
            continue
        prompt = lines[i - 1] if i >= 1 else None
        if prompt is None or prompt.voice.lower() == learner:
            continue
        if line.text.lower() in answers_seen:
            continue
        answers_seen.add(line.text.lower())

        setup = None
        if prompt.voice in ("Man", "Woman"):
            before = lines[i - 2] if i >= 2 else None
            setup = before.text if before and before.voice == "Teacher" else None

        found.append(Card(
            setup=setup,
            prompt=(prompt.voice.lower(), prompt.text),
            answer=(line.voice.lower(), line.text),
        ))
    return found


def _clean(text):
    text = re.sub(r"\s*\[[^\]]*\]", "", text)
    return text.strip()


_LABELS = {"teacher": "Teacher", "teacherl2": "TeacherL2", "man": "Man", "woman": "Woman"}


def card_lines(card, values):
    """A card said: the setup of an exchange, the line the learner answers, the
    time to answer, then the answer twice."""
    out = []
    if card.setup:
        out.append(_line("Teacher", card.setup, 1))
    out.append(_line(_LABELS[card.prompt[0]], card.prompt[1], time_to_answer(card.answer[1], values)))
    out += [_line(_LABELS[card.answer[0]], card.answer[1], values["repeat_pause"])] * 2
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
