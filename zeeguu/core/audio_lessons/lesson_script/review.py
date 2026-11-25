"""
How a review of earlier lessons is said, and where it goes in the lesson.
What to review is chosen by lesson_review.py.
"""

from zeeguu.core.audio_lessons.lesson_script.challenges import challenge_lines
from zeeguu.core.audio_lessons.lesson_script.markers import VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import PAUSE_AT_LANGUAGE_SWITCH, SpokenLine
from zeeguu.core.audio_lessons.lesson_script.voices import PEOPLE, TEACHERS

# How a segment joined to the next one ends, written out.
_JOINED = str(SpokenLine("teacher", "", PAUSE_AT_LANGUAGE_SWITCH)).split(" ", 1)[-1].strip()


def review_lines(challenges, values):
    """The review: the challenges to review, in order, each said as it is
    (challenge_lines), with a blank line before each."""
    out = []
    for challenge in challenges:
        out.append("")
        out += challenge_lines(challenge, values)
    return out


def with_review(expanded, review):
    """
    The expanded script with the review lines put before the closing dialogue
    and the Teacher's sentence that introduces it ("Listen again..."): before
    the last run of the two people's lines, and the Teacher lines right before
    it (a sentence with «chevrons» is several of them). Nothing to put: the
    script as it was.
    """
    if not review:
        return expanded
    lines = expanded.rstrip("\n").split("\n")
    at = closing_dialogue_start(lines)
    review = [str(line) for line in review]
    return "\n".join(lines[:at] + review + [""] + lines[at:]) + "\n"


def closing_dialogue_start(lines):
    """Where the closing dialogue starts, with the Teacher sentence before it."""
    voices = [_voice(line) for line in lines]
    people = [i for i, voice in enumerate(voices) if voice in PEOPLE]
    if not people:
        return len(lines)
    at = people[-1]
    while at > 0 and voices[at - 1] in PEOPLE:
        at -= 1
    while at > 0 and voices[at - 1] in TEACHERS:
        at -= 1
    return at


def _voice(line):
    voice_line = VOICE_LINE.match(line.strip())
    return voice_line.group(1).lower() if voice_line else None


def voice_line_count(lines):
    """
    How many lines are said, as SECONDS_PER_LINE counts them: a Teacher
    sentence with «chevrons» is one line, though written as several segments
    (each but the last followed by PAUSE_AT_LANGUAGE_SWITCH).
    """
    count, continues = 0, False
    for line in lines:
        voice = _voice(line)
        if voice is None:
            continues = False
            continue
        if not (continues and voice in TEACHERS):
            count += 1
        continues = voice in TEACHERS and line.rstrip().endswith(_JOINED)
    return count
