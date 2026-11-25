"""
How a review of earlier lessons is said, and where it goes in the lesson.
What to review is chosen by lesson_review.py.
"""

from zeeguu.core.audio_lessons.lesson_script.challenges import challenge_lines
from zeeguu.core.audio_lessons.lesson_script.markers import REVIEW_SLOT, VOICE_LINE
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
    The expanded script with the review lines where the model put [review];
    in a script without one (prompt v4), before the closing dialogue
    and the Teacher's sentence that introduces it ("Listen again..."): before
    the last run of the two people's lines, and the Teacher lines right before
    it (a sentence with «chevrons» is several of them). Nothing to put: the
    script as it was.
    """
    lines = expanded.rstrip("\n").split("\n")
    review = [str(line) for line in review]
    if REVIEW_SLOT in lines:
        # Where the model put [review], after its Teacher line introducing it.
        # Nothing to review: both go, the introduction would promise nothing.
        at = lines.index(REVIEW_SLOT)
        if review:
            return "\n".join(lines[:at] + review + lines[at + 1:]) + "\n"
        intro = at
        while intro > 0 and _voice(lines[intro - 1]) in TEACHERS:
            intro -= 1
        return "\n".join(lines[:intro] + lines[at + 1:]).strip("\n") + "\n"
    if not review:
        return expanded
    at = closing_dialogue_start(lines)
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
