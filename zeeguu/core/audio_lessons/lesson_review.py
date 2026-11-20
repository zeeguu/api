"""
What an A0 lesson reviews from the learner's earlier lessons: chosen by code,
not by the model, and placed by code (lesson_markup.with_review).

An earlier lesson comes back at growing distances, like a word in the
exercises: it is due a day after it was heard, then 2 days after its first
review, 4 after its second, and so on (a review counts once the learner heard
the lesson that made it). The most overdue come first, the most recent first
among equals, and lessons are added until the lesson is as long as the learner
asked for: a lesson not yet due is still reviewed when the length needs it.

What a lesson reviewed is stored (AudioLessonReview), so the next lesson's
spacing knows it. Only whole dialogues for now; the table also allows single
questions from earlier lessons' marked scripts.
"""

from datetime import datetime

FIRST_INTERVAL_DAYS = 1


def due_order(heard, now=None):
    """The earlier lessons that can be reviewed, most overdue first."""
    now = now or datetime.utcnow()
    candidates = [h for h in heard if h.dialogue and h.learner and h.dialogue_id is not None]

    def overdue(lesson):
        seen = [lesson.heard_at] + [
            other.heard_at for other in heard if lesson.dialogue_id in (other.reviewed or ())
        ]
        seen = [t for t in seen if t is not None]
        if not seen:
            return 0.0, datetime.min
        interval = FIRST_INTERVAL_DAYS * 2 ** (len(seen) - 1)
        days = (now - max(seen)).total_seconds() / 86400
        return days / interval, lesson.heard_at or datetime.min

    return sorted(candidates, key=lambda lesson: overdue(lesson), reverse=True)


def choose(heard, lines_needed, lines_per_review, now=None):
    """
    The lessons to review, in order, until they add `lines_needed` voice
    lines. lines_per_review(lesson) is what reviewing one adds.
    """
    chosen, lines = [], 0
    for lesson in due_order(heard, now):
        if lines >= lines_needed:
            break
        chosen.append(lesson)
        lines += lines_per_review(lesson)
    return chosen
