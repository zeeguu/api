from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from zeeguu.core.model.db import db


class AudioLessonCard(db.Model):
    """
    One question and answer of an A0 lesson, for later lessons to review
    (audio_lessons/lesson_review.py). Written when the lesson is made, from its
    marked script (lesson_markup.cards): the Teacher's question in the
    learner's own language, so the meaning is always given; the answer; and the
    line the question answers ("Answer her."), when the model marked one [cue].
    """

    __tablename__ = "audio_lesson_card"
    __table_args__ = (
        UniqueConstraint("dialogue_id", "position", name="uq_card_position"),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)
    dialogue_id = Column(Integer, ForeignKey("audio_lesson_dialogue.id"), nullable=False)
    position = Column(Integer, nullable=False)
    question = Column(String(500), nullable=False)
    answer_voice = Column(String(5), nullable=False)
    answer = Column(String(500), nullable=False)
    cue_voice = Column(String(5), nullable=True)
    cue = Column(String(500), nullable=True)

    def __init__(self, dialogue_id, position, card):
        """card: lesson_markup.Card."""
        self.dialogue_id = dialogue_id
        self.position = position
        self.question = card.prompt[:500]
        self.answer_voice, answer = card.answer
        self.answer = answer[:500]
        if card.context:
            self.cue_voice, cue = card.context
            self.cue = cue[:500]

    def as_card(self):
        from zeeguu.core.audio_lessons.lesson_markup import Card

        context = (self.cue_voice, self.cue) if self.cue else None
        return Card(context, self.question, (self.answer_voice, self.answer))

    @classmethod
    def for_dialogues(cls, dialogue_ids):
        """{dialogue_id: ((card id, Card), ...)} in order."""
        rows = (
            cls.query.filter(cls.dialogue_id.in_(list(dialogue_ids)))
            .order_by(cls.dialogue_id, cls.position)
            .all()
            if dialogue_ids
            else []
        )
        out = {}
        for row in rows:
            out.setdefault(row.dialogue_id, []).append((row.id, row.as_card()))
        return {k: tuple(v) for k, v in out.items()}
