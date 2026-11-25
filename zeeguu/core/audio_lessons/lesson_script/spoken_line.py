"""
SpokenLine: one line of the expanded script. And how a line with «chevrons»
in it is said: a learned-language word inside a Teacher sentence, «kaffe»,
said by the teacher's own voice in the learned language (TeacherL2), joined
to the rest of the sentence. "The word for coffee is «kaffe»." is three
segments, not three lines the model has to write. Chirp 3 HD voices take no
SSML to switch language within a sentence, so the switch is made in segments.
"""

import re
from dataclasses import dataclass

from zeeguu.core.audio_lessons.lesson_script.voices import TEACHER, TEACHER_L2, label

# One «…» span, with the punctuation right after it: "«kaffe». Say it." is
# "kaffe." then "Say it.", not "kaffe" then a lone ".".
CHEVRON_SPAN = re.compile(r"«([^»]+)»([.,!?;:…]*)")

# Pause where a Teacher sentence switches between the teacher's two
# languages, before and after a «…» span. None: each synthesized segment
# already starts and ends with a little silence, and listened side by side
# (25 Nov 2026), the sentence without an added pause sounded better than
# with 0.3 s. Tune by ear.
PAUSE_AT_LANGUAGE_SWITCH = 0


@dataclass(frozen=True)
class SpokenLine:
    """One line of the expanded script: who says what, slowly or not, and the
    silence after it. Formatted as a script line only when the script is
    written out (str)."""

    voice: str  # "teacher", "teacherl2", "man" or "woman"
    text: str
    pause: float  # seconds of silence after it
    slow: bool = False  # said slowly, once, as a new word is

    def __str__(self):
        slow = " [slow]" if self.slow else ""
        return f"{label(self.voice)}: {self.text}{slow} [{_seconds(self.pause)} seconds]"


def _seconds(value):
    return int(value) if float(value).is_integer() else value


def spoken_lines(voice, text, pause) -> list:
    """
    The SpokenLines that say `text`, followed by `pause` seconds. A Teacher
    line with «…» in it becomes segments: the text between the spans in the
    Teacher's voice, each span in the teacher's learned-language voice
    (TeacherL2), joined by PAUSE_AT_LANGUAGE_SWITCH. In any other line the
    chevrons are just dropped.
    """
    if voice != TEACHER or "«" not in text:
        return [SpokenLine(voice, without_chevrons(text), pause)]

    segments = []
    position = 0
    for span in CHEVRON_SPAN.finditer(text):
        teacher_text = text[position:span.start()].strip()
        if teacher_text:
            segments.append((TEACHER, teacher_text))
        learned_text, punctuation = span.groups()
        segments.append((TEACHER_L2, learned_text.strip() + punctuation))
        position = span.end()
    rest = text[position:].strip()
    if rest:
        segments.append((TEACHER, rest))

    *joined, last = segments
    return [SpokenLine(v, t, PAUSE_AT_LANGUAGE_SWITCH) for v, t in joined] + [SpokenLine(*last, pause)]


def without_chevrons(text):
    """The text with «…» around a span removed, the span and its punctuation kept."""
    return CHEVRON_SPAN.sub(r"\1\2", text)
