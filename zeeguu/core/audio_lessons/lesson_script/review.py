"""
How a review of earlier lessons is said, and where it goes in the lesson.
What to review is chosen by lesson_review.py.
"""

from zeeguu.core.audio_lessons.lesson_script.challenges import challenge_lines
from zeeguu.core.audio_lessons.lesson_script.markers import VOICE_LINE
from zeeguu.core.audio_lessons.lesson_script.spoken_line import SpokenLine, spoken_lines
from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer
from zeeguu.core.audio_lessons.lesson_script.voices import TEACHER


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
        if voice == learner:
            out.append(SpokenLine(voice, text, values["repeat_pause"]))
        else:
            learner_next = i + 1 < len(dialogue) and dialogue[i + 1][0] == learner
            pause = time_to_answer(dialogue[i + 1][1], values) if learner_next else 1
            out.append(SpokenLine(voice, text, pause))
    return out


def review_lines(items, values):
    """
    The review (lesson_review.ReviewItem, in order), as SpokenLines with a
    blank line before each item: challenges as they are; a whole dialogue,
    for a lesson with no challenges, opened by its title, said by the Teacher
    (titles are in the learner's own language).
    """
    out = []
    for item in items:
        out.append("")
        if item.challenge is not None:
            out += challenge_lines(item.challenge, values)
        else:
            out += spoken_lines(TEACHER, f"{item.lesson.title}.", 1)
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
    review = [str(line) for line in review]
    return "\n".join(lines[:last_teacher] + review + [""] + lines[last_teacher:]) + "\n"


def voice_line_count(lines):
    return sum(1 for line in lines if VOICE_LINE.match(line.strip()))
