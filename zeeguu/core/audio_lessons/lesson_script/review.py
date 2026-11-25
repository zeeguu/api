"""
How a review of earlier lessons is said, and where it goes in the lesson.
What to review is chosen by lesson_review.py.
"""

from zeeguu.core.audio_lessons.lesson_script.challenges import challenge_lines
from zeeguu.core.audio_lessons.lesson_script.markers import VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import SpokenLine
from zeeguu.core.audio_lessons.lesson_script.voices import PEOPLE, TEACHERS


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
    """Where the closing dialogue starts, with the Teacher sentence before it
    (blank lines between them included)."""
    voices = [_voice(line) for line in lines]
    people = [i for i, voice in enumerate(voices) if voice in PEOPLE]
    if not people:
        return len(lines)
    at = people[-1]
    while at > 0 and voices[at - 1] in PEOPLE:
        at -= 1
    before = at
    while before > 0 and not lines[before - 1].strip():
        before -= 1
    intro = before
    while intro > 0 and voices[intro - 1] in TEACHERS:
        intro -= 1
    return intro if intro < before else at


def _voice(line):
    voice_line = VOICE_LINE.match(line.strip())
    return voice_line.group(1).lower() if voice_line else None


def said_line_count(lines):
    """
    How many lines are said, as SECONDS_PER_LINE counts them, in expand_lines'
    output: a Teacher sentence with «chevrons» is one line, though it is
    several segments (SpokenLine.joined).
    """
    return sum(1 for line in lines if isinstance(line, SpokenLine) and not line.joined)
