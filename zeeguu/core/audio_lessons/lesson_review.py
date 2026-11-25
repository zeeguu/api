"""
What an A0 lesson reviews from the learner's earlier lessons: chosen by code,
not by the model, and placed by code (lesson_markup.with_review).

The review is retrieval, not listening again: being asked to recall
something helps memory more than meeting it again (the testing effect,
Roediger & Karpicke 2006), and learners left to choose prefer listening again,
which feels fluent and does less (Kornell & Bjork 2008). So it is cards: one
question and answer of an earlier lesson (AudioLessonCard), the question in
the learner's own language so the meaning is always given, then time to
answer, then the answer. A lesson from before cards has none; its dialogue is
reviewed instead, answered line by line in the learner's role.

Each card (or fallback dialogue) comes back at growing distances, as in
Pimsleur's graduated interval recall: due a day after its lesson was heard,
then 2 days after its first review, 4 after its second, and so on (a review
counts once the learner heard the lesson that made it). The most overdue come
first, the most recent first among equals, and items are added until the
lesson is as long as the learner asked for: an item not yet due is still
reviewed when the length needs it.

What a lesson reviewed is stored (AudioLessonReview: kind "card" with the
card's id, or "dialogue"), so the next lesson's spacing knows it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from zeeguu.core.audio_lessons.lesson_markup import Card, card_lines, respond_lines
from zeeguu.core.audio_lessons.words_heard import HeardLesson

FIRST_INTERVAL_DAYS = 1

@dataclass(frozen=True)
class ReviewItem:
    """Something an earlier lesson offers for review: one of its cards, or its whole dialogue."""

    lesson: HeardLesson
    card: Optional[Card]  # None: the whole dialogue (a lesson from before cards)
    card_id: Optional[int]  # its AudioLessonCard

CARD = "card"  # AudioLessonReview.kind
DIALOGUE = "dialogue"


def items_of(lesson, learner):
    """
    A lesson's cards; or, when it has none, its dialogue as one item. Only
    what was made with the learner's current voice: in many languages a
    learner's words depend on their gender, so a card answered as a woman is
    not asked of the same learner as a man.
    """
    if lesson.cards:
        return [
            ReviewItem(lesson, card, card_id)
            for card_id, card in lesson.cards
            if card.answer[0] == learner
        ]
    if lesson.dialogue and lesson.learner == learner:
        return [ReviewItem(lesson, None, None)]
    return []


def kind(item):
    return DIALOGUE if item.card is None else CARD


def due_order(heard, learner, now=None):
    """Everything the earlier lessons offer for review, most overdue first."""
    now = now or datetime.utcnow()
    items = [
        item
        for lesson in heard
        if lesson.dialogue_id is not None
        for item in items_of(lesson, learner)
    ]

    def overdue(item):
        key = (item.lesson.dialogue_id, item.card_id)
        seen = [item.lesson.heard_at] + [
            other.heard_at for other in heard if key in (other.reviewed or ())
        ]
        seen = [t for t in seen if t is not None]
        if not seen:
            return 0.0, datetime.min
        interval = FIRST_INTERVAL_DAYS * 2 ** (len(seen) - 1)
        days = (now - max(seen)).total_seconds() / 86400
        return days / interval, item.lesson.heard_at or datetime.min

    return sorted(items, key=overdue, reverse=True)


def lines_of(item, values):
    if item.card is not None:
        return len(card_lines(item.card, values))
    return 1 + len(respond_lines(item.lesson.dialogue, item.lesson.learner, values))


def choose(heard, lines_needed, values, learner, now=None):
    """The items to review, in order, until they add `lines_needed` voice lines."""
    chosen, lines = [], 0
    for item in due_order(heard, learner, now):
        if lines >= lines_needed:
            break
        chosen.append(item)
        lines += lines_of(item, values)
    return chosen
