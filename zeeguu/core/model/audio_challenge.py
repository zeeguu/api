from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from zeeguu.core.model.db import db


class AudioChallenge(db.Model):
    """
    One thing the learner answered in an A0 lesson, for later lessons to review
    (audio_lessons/lesson_review.py). Written when the lesson is made, from its
    marked script (lesson_script.challenges). A QUESTION: the Teacher's question in
    the learner's own language, then the answer. An EXCHANGE: the Teacher's
    setup, the Other person's line, then the answer. answer_voice is the voice
    the learner had: a challenge is reviewed only while the learner has that voice,
    since in many languages the words depend on the speaker's gender.
    """

    __tablename__ = "audio_challenge"
    __table_args__ = (
        UniqueConstraint("dialogue_id", "position", name="uq_challenge_position"),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    id = Column(Integer, primary_key=True)
    dialogue_id = Column(Integer, ForeignKey("audio_lesson_dialogue.id"), nullable=False)
    position = Column(Integer, nullable=False)
    setup = Column(String(500), nullable=True)
    prompt_voice = Column(String(9), nullable=False)
    prompt = Column(String(500), nullable=False)
    answer_voice = Column(String(5), nullable=False)
    answer = Column(String(500), nullable=False)

    def __init__(self, dialogue_id, position, challenge):
        """challenge: lesson_script.challenges.Challenge."""
        self.dialogue_id = dialogue_id
        self.position = position
        self.setup = challenge.setup[:500] if challenge.setup else None
        self.prompt_voice, prompt = challenge.prompt
        self.prompt = prompt[:500]
        self.answer_voice, answer = challenge.answer
        self.answer = answer[:500]

    def as_challenge(self):
        from zeeguu.core.audio_lessons.lesson_script.challenges import Challenge

        return Challenge(self.setup, (self.prompt_voice, self.prompt), (self.answer_voice, self.answer))

    @classmethod
    def for_dialogues(cls, dialogue_ids):
        """{dialogue_id: ((challenge id, Challenge), ...)} in order."""
        rows = (
            cls.query.filter(cls.dialogue_id.in_(list(dialogue_ids)))
            .order_by(cls.dialogue_id, cls.position)
            .all()
            if dialogue_ids
            else []
        )
        out = {}
        for row in rows:
            out.setdefault(row.dialogue_id, []).append((row.id, row.as_challenge()))
        return {k: tuple(v) for k, v in out.items()}
