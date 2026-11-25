"""
What the learner answered in a lesson, kept for later lessons to review: a
QUESTION (the Teacher asks, the learner answers) or an EXCHANGE (the Teacher
sets it up, the Other person speaks, the learner answers them). Read once from
a new lesson's marked script and stored (AudioChallenge).
"""

import re
from dataclasses import dataclass
from typing import Optional

from zeeguu.core.audio_lessons.lesson_script.markers import LINE_MARKER, VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import SpokenLine, spoken_lines
from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer


@dataclass(frozen=True)
class Challenge:
    """One thing the learner answered in a lesson: a question or an exchange."""

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
        voice_line = VOICE_LINE.match(raw.strip())
        if not voice_line:
            continue
        voice, text = voice_line.groups()
        marker = LINE_MARKER.search(text)
        lines.append(MarkedLine(voice, _clean(text), marker.group(1).lower() if marker else None))
    return lines


def _clean(text):
    return re.sub(r"\s*\[[^\]]*\]", "", text).strip()


def challenges(marked, learner):
    """
    The challenges of a marked script (with voices), in order. A challenge is
    an [answer] by the learner and the line right before it, which the learner
    answers: a Teacher question, or the Other person's line in an exchange,
    then with the Teacher's setup before it when there is one. One challenge
    per answer: a lesson recalls the same phrase several times, and its first
    question is usually the one that says what it means.

    A second [answer] right after the first (two answers to one question)
    makes no challenge of its own: the line before it is the learner's.
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

        found.append(Challenge(
            setup=setup,
            prompt=(prompt.voice.lower(), prompt.text),
            answer=(line.voice.lower(), line.text),
        ))
    return found


_LABELS = {"teacher": "Teacher", "teacherl2": "TeacherL2", "man": "Man", "woman": "Woman"}


def challenge_lines(challenge, values):
    """A challenge said: the setup of an exchange, the line the learner
    answers, the time to answer, then the answer twice."""
    out = []
    if challenge.setup:
        out += spoken_lines("Teacher", challenge.setup, 1)
    out += spoken_lines(_LABELS[challenge.prompt[0]], challenge.prompt[1], time_to_answer(challenge.answer[1], values))
    out += [SpokenLine(_LABELS[challenge.answer[0]], challenge.answer[1], values["repeat_pause"])] * 2
    return out
