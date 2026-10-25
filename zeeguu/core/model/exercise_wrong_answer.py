from sqlalchemy.dialects import mysql

from zeeguu.core.model.db import db
from zeeguu.core.model.exercise import Exercise


class ExerciseWrongAnswer(db.Model):
    """
    What the learner answered in a wrong attempt of an exercise: the typed
    text, or the option picked in a multiple-choice exercise. The outcome
    ("WWC") only says that the attempts were wrong.
    """

    __tablename__ = "exercise_wrong_answer"
    __table_args__ = (
        db.UniqueConstraint("exercise_id", "attempt_i", name="uq_exercise_wrong_answer"),
    )

    # Longer answers are cut. They are kept for analysis, not looked up by
    # their text, so a cut answer does no harm.
    MAX_LENGTH = 255
    # More than any learner gives before asking for the solution.
    MAX_PER_EXERCISE = 20

    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(
        db.Integer, db.ForeignKey(Exercise.id, ondelete="CASCADE"), nullable=False
    )
    # 0, 1, 2, ... in the order the learner gave them
    attempt_i = db.Column(db.Integer, nullable=False)
    answer = db.Column(
        db.String(MAX_LENGTH).with_variant(mysql.VARCHAR(MAX_LENGTH, collation="utf8mb4_bin"), "mysql"),
        nullable=False,
    )

    # passive_deletes: on an exercise delete the FK's ON DELETE CASCADE
    # removes the rows; the ORM does not load them first.
    exercise = db.relationship(
        Exercise,
        backref=db.backref(
            "wrong_answers",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by="ExerciseWrongAnswer.attempt_i",
        ),
    )

    def __init__(self, exercise, attempt_i, answer):
        self.exercise = exercise
        self.attempt_i = attempt_i
        self.answer = answer

    @classmethod
    def add_all(cls, db_session, exercise, answers):
        """Blank answers are skipped; the rest are numbered in order."""
        answers = [a.strip()[: cls.MAX_LENGTH] for a in answers if a and a.strip()]
        for i, answer in enumerate(answers[: cls.MAX_PER_EXERCISE]):
            db_session.add(cls(exercise, i, answer))
