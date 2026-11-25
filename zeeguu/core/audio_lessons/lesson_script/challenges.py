"""
What the learner answered in a lesson, kept for later lessons to review: a
QUESTION (the Teacher asks, the learner answers) or an EXCHANGE (the Teacher
sets it up, the Other person speaks, the learner answers them). Read once from
a new lesson's marked script and stored (AudioChallenge).
"""

import re
from dataclasses import dataclass
from typing import Optional

from zeeguu.core.audio_lessons.lesson_script.markers import DIALOGUE_MARKER, LINE_MARKER, REVIEW_MARKER, VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import SpokenLine, spoken_lines, without_chevrons
from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer
from zeeguu.core.audio_lessons.lesson_script.voices import PEOPLE, TEACHER, TEACHERS


@dataclass(frozen=True)
class Utterance:
    """Something one voice says: in a challenge, the prompt or the answer."""

    voice: str  # "teacher", "teacherl2", "man" or "woman"
    text: str


@dataclass(frozen=True)
class Challenge:
    """One thing the learner answered in a lesson: a question or an exchange."""

    setup: Optional[str]  # the Teacher's setup of an exchange, in the learner's language; None for a question
    prompt: Utterance  # the line the learner answers: the Teacher's question, or the Other person's line
    answer: Utterance  # the learner's answer

    @property
    def kind(self):
        return "question" if self.prompt.voice in TEACHERS else "exchange"


@dataclass(frozen=True)
class MarkedLine:
    """One voice line of a marked script."""

    voice: Optional[str]  # "teacher", "teacherl2", "man" or "woman"; None for [dialogue]
    text: str  # what is said, without markers
    marker: Optional[str]  # "drill", "answer", "understand", "dialogue", or None


def marked_lines(marked) -> list:
    """
    The voice lines of a marked script, in order, and each [dialogue] as a
    line with no voice: where the dialogue is played, the line before an
    answer is the dialogue's last, not the line before [dialogue]. The title
    and blank lines are left out. «Chevrons» are dropped outside Teacher lines,
    as expand() drops them.
    """
    lines = []
    for raw in (marked or "").split("\n"):
        if DIALOGUE_MARKER.match(raw.strip()) or REVIEW_MARKER.match(raw.strip()):
            lines.append(MarkedLine(None, "", "dialogue"))
            continue
        voice_line = VOICE_LINE.match(raw.strip())
        if not voice_line:
            continue
        voice, text = voice_line.groups()
        voice = voice.lower()
        marker = LINE_MARKER.search(text)
        text = _clean(text) if voice == TEACHER else without_chevrons(_clean(text))
        lines.append(MarkedLine(voice, text, marker.group(1).lower() if marker else None))
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
        if line.marker != "answer" or line.voice != learner:
            continue
        prompt = lines[i - 1] if i >= 1 else None
        if prompt is None or prompt.voice in (learner, None):
            continue
        if line.text.lower() in answers_seen:
            continue
        answers_seen.add(line.text.lower())

        setup = None
        if prompt.voice in PEOPLE:
            before = lines[i - 2] if i >= 2 else None
            setup = before.text if before and before.voice == TEACHER else None

        found.append(Challenge(
            setup=setup,
            prompt=Utterance(prompt.voice, prompt.text),
            answer=Utterance(line.voice, line.text),
        ))
    return found


def dialogue_challenges(dialogue, learner):
    """
    The challenges a dialogue makes on its own: each line of the learner
    after a line of the other person is an exchange, without a setup (hear
    the line, answer it). For lessons written before challenges were kept:
    tools/backfill_a0_challenges.py. dialogue: [(voice, text)].
    """
    found, answers_seen = [], set()
    for (voice_before, text_before), (voice, text) in zip(dialogue, dialogue[1:]):
        if voice != learner or voice_before == learner or text.lower() in answers_seen:
            continue
        answers_seen.add(text.lower())
        found.append(Challenge(None, Utterance(voice_before, text_before), Utterance(voice, text)))
    return found


def challenge_lines(challenge, values):
    """A challenge said: the setup of an exchange, the line the learner
    answers, the time to answer, then the answer twice."""
    out = []
    if challenge.setup:
        out += spoken_lines(TEACHER, challenge.setup, 1)
    out += spoken_lines(challenge.prompt.voice, challenge.prompt.text, time_to_answer(challenge.answer.text, values))
    out += [SpokenLine(challenge.answer.voice, challenge.answer.text, values["repeat_pause"])] * 2
    return out
