"""
How a review of earlier lessons is said, and where it goes in the lesson.
What to review is chosen by lesson_review.py.
"""

from zeeguu.core.audio_lessons.lesson_script.challenges import challenge_lines
from zeeguu.core.audio_lessons.lesson_script.markers import VOICE_LINE


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
    The expanded script with the review lines put before the closing dialogue:
    before the Teacher's line that introduces it ("Listen again..."), found
    as the last Teacher line. Nothing to put: the script as it was.
    """
    if not review:
        return expanded
    lines = expanded.rstrip("\n").split("\n")
    last_teacher = max((i for i, l in enumerate(lines) if l.startswith("Teacher:")), default=len(lines))
    review = [str(line) for line in review]
    return "\n".join(lines[:last_teacher] + review + [""] + lines[last_teacher:]) + "\n"


def voice_line_count(lines):
    return sum(1 for line in lines if VOICE_LINE.match(line.strip()))
