from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint

from zeeguu.core.model.db import db


class AudioLessonReview(db.Model):
    """
    A challenge from an earlier A0 lesson that a lesson reviews, at its place
    in the review (position 0 first). Chosen and placed by code
    (audio_lessons/lesson_review.py), not by the model; the spacing of the
    next reviews is read from these rows.
    """

    __tablename__ = "audio_lesson_review"
    __table_args__ = (
        UniqueConstraint("dialogue_id", "position", name="uq_review_position"),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)
    dialogue_id = Column(Integer, ForeignKey("audio_lesson_dialogue.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("audio_challenge.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)

    def __init__(self, dialogue_id, challenge_id, position):
        self.dialogue_id = dialogue_id
        self.challenge_id = challenge_id
        self.position = position

    @classmethod
    def reviewed_by(cls, dialogue_ids):
        """{dialogue_id: (the challenge ids it reviewed, in order)}."""
        rows = (
            cls.query.filter(cls.dialogue_id.in_(list(dialogue_ids)))
            .order_by(cls.dialogue_id, cls.position)
            .all()
            if dialogue_ids
            else []
        )
        out = {}
        for row in rows:
            out.setdefault(row.dialogue_id, []).append(row.challenge_id)
        return {k: tuple(v) for k, v in out.items()}
