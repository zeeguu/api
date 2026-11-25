"""
What an A0 lesson reviews from the learner's earlier lessons: chosen by code,
not by the model, and placed by code (lesson_script.review.with_review).

The review is retrieval, not listening again: being asked to recall
something helps memory more than meeting it again (the testing effect,
Roediger & Karpicke 2006), and learners left to choose prefer listening again,
which feels fluent and does less (Kornell & Bjork 2008). So it is
challenges: what the learner answered in an earlier lesson (AudioChallenge),
a prompt, time to answer, then the answer.

Each challenge comes back at growing distances, as in Pimsleur's graduated
interval recall: due a day after its lesson was heard, then 2 days after its
first review, 4 after its second, and so on (a review counts once the learner
heard the lesson that made it). The most overdue come first, the most recent
first among equals, and challenges are added until the lesson is as long as
the learner asked for: one not yet due is still reviewed when the length
needs it.

What a lesson reviewed is stored (AudioLessonReview), so the next lesson's
spacing knows it.
"""

from datetime import datetime

from zeeguu.core.audio_lessons.lesson_script.challenges import challenge_lines

FIRST_INTERVAL_DAYS = 1


def due_challenges(heard, learner, now=None):
    """
    The challenges of the earlier lessons, as (challenge id, Challenge), most
    overdue first. Only those answered in the learner's current voice: in
    many languages a learner's words depend on their gender, so a challenge
    answered as a woman is not asked of the same learner as a man.
    """
    now = now or datetime.utcnow()

    def overdue(lesson, challenge_id):
        seen = [lesson.heard_at] + [other.heard_at for other in heard if challenge_id in other.reviewed]
        seen = [t for t in seen if t is not None]
        if not seen:
            return 0.0, datetime.min
        interval = FIRST_INTERVAL_DAYS * 2 ** (len(seen) - 1)
        days = (now - max(seen)).total_seconds() / 86400
        return days / interval, lesson.heard_at or datetime.min

    candidates = [
        (overdue(lesson, challenge_id), challenge_id, challenge)
        for lesson in heard
        for challenge_id, challenge in lesson.challenges
        if challenge.answer.voice == learner
    ]
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    # One challenge per answer: several lessons ask for "Tak.", and a review
    # asks for it once, the most overdue of them.
    due, answers = [], set()
    for _, challenge_id, challenge in candidates:
        answer = challenge.answer.text.strip().lower()
        if answer not in answers:
            answers.add(answer)
            due.append((challenge_id, challenge))
    return due


def choose(heard, lines_needed, values, learner, now=None):
    """The challenges to review, as (challenge id, Challenge), in order, until
    they add `lines_needed` voice lines."""
    chosen, lines = [], 0
    for challenge_id, challenge in due_challenges(heard, learner, now):
        if lines >= lines_needed:
            break
        chosen.append((challenge_id, challenge))
        lines += len(challenge_lines(challenge, values))
    return chosen
