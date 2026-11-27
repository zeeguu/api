
import zeeguu.core

from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.exercise_source import ExerciseSource
from zeeguu.core.model.user_exercise_session import UserExerciseSession

from zeeguu.core.model.db import db
from zeeguu.core.model.user_word import UserWord


class Exercise(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "exercise"

    id = db.Column(db.Integer, primary_key=True)
    outcome_id = db.Column(
        db.Integer, db.ForeignKey(ExerciseOutcome.id), nullable=False
    )
    outcome = db.relationship(ExerciseOutcome)
    source_id = db.Column(db.Integer, db.ForeignKey(ExerciseSource.id), nullable=False)
    source = db.relationship(ExerciseSource)
    solving_speed = db.Column(db.Integer)
    time = db.Column(db.DateTime, nullable=False)
    feedback = db.Column(db.String(255))

    session_id = db.Column(
        db.Integer, db.ForeignKey(UserExerciseSession.id), nullable=True
    )
    session = db.relationship(UserExerciseSession)

    user_word_id = db.Column(db.Integer, db.ForeignKey(UserWord.id), nullable=False)
    user_word = db.relationship(
        UserWord,
        backref=db.backref("exercise_log", order_by="Exercise.id"),
    )

    # Which bookmark (sentence context) was shown in this exercise, recorded
    # before any post-exercise context rotation. Nullable plain INT (no FK) so
    # the migration is instant on MySQL 8 and bookmark deletions keep history.
    # NULL for historical rows and context-free sources (Match, audio lessons,
    # verbal flashcards).
    bookmark_id = db.Column(db.Integer, nullable=True)

    def __init__(
        self,
        outcome,
        source,
        solving_speed,
        time,
        session_id,
        user_word,
        feedback="",
        bookmark_id=None,
    ):
        self.outcome = outcome
        self.source = source
        self.solving_speed = solving_speed
        self.time = time
        self.feedback = feedback
        self.session_id = session_id
        self.user_word = user_word
        self.bookmark_id = bookmark_id

    def short_string_summary(self):
        return str(self.source.id) + self.outcome.outcome[0]

    def __str__(self):
        return f"{self.source.source} " + str(self.time) + f" {self.outcome.outcome}"

    def __repr__(self):
        return self.__str__()

    @classmethod
    def find(cls, user_id=None):
        """
        Find all the exercises for a particular or for all users

        Parameters:
        user_id = user identifier

        return: list of exercises sorted by time in ascending order
        """
        query = cls.query
        if user_id is not None:
            query = query.join(UserWord).filter(UserWord.user_id == user_id)
        query = query.order_by("time")

        return query.all()

    def is_too_easy(self):
        return self.outcome.outcome in ExerciseOutcome.too_easy_outcomes

    def is_correct(self):
        return ExerciseOutcome.is_correct(self.outcome.outcome)
