from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from zeeguu.core.model.db import db


class AudioLessonReview(db.Model):
    """
    Something from an earlier A0 lesson that a lesson reviews, at its place in
    the review (position 0 first). Chosen and placed by code
    (audio_lessons/lesson_review.py), not by the model; the spacing of the next
    reviews is read from these rows.

    kind "card": one of the earlier lesson's cards (AudioLessonCard).
    kind "dialogue": the earlier lesson's whole dialogue, answered in the
    learner's role (card_id None), for a lesson from before cards.
    """

    DIALOGUE = "dialogue"
    CARD = "card"

    __tablename__ = "audio_lesson_review"
    __table_args__ = (
        UniqueConstraint("dialogue_id", "position", name="uq_review_position"),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)
    dialogue_id = Column(Integer, ForeignKey("audio_lesson_dialogue.id"), nullable=False)
    reviewed_dialogue_id = Column(
        Integer, ForeignKey("audio_lesson_dialogue.id"), nullable=False, index=True
    )
    kind = Column(String(10), nullable=False)
    card_id = Column(Integer, ForeignKey("audio_lesson_card.id"), nullable=True)
    position = Column(Integer, nullable=False)

    def __init__(self, dialogue_id, reviewed_dialogue_id, position, kind=DIALOGUE, card_id=None):
        self.dialogue_id = dialogue_id
        self.reviewed_dialogue_id = reviewed_dialogue_id
        self.position = position
        self.kind = kind
        self.card_id = card_id

    @classmethod
    def reviewed_by(cls, dialogue_ids):
        """{dialogue_id: ((reviewed dialogue id, card id or None), ...)} in order."""
        rows = (
            cls.query.filter(cls.dialogue_id.in_(list(dialogue_ids)))
            .order_by(cls.dialogue_id, cls.position)
            .all()
            if dialogue_ids
            else []
        )
        out = {}
        for row in rows:
            out.setdefault(row.dialogue_id, []).append((row.reviewed_dialogue_id, row.card_id))
        return {k: tuple(v) for k, v in out.items()}
