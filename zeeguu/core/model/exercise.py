import zeeguu.core

from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.exercise_source import ExerciseSource
from zeeguu.core.model.user_exercise_session import UserExerciseSession

from zeeguu.core.model import db


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

    session_id = db.Column(db.Integer, db.ForeignKey(UserExerciseSession.id), nullable=True)
    session = db.relationship(UserExerciseSession)

    def __init__(self, outcome, source, solving_speed, time, session_id, feedback=""):
        self.outcome = outcome
        self.source = source
        self.solving_speed = solving_speed
        self.time = time
        self.feedback = feedback
        self.session_id = session_id

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
        from zeeguu.core.model.bookmark import Bookmark, bookmark_exercise_mapping

        query = cls.query
        if user_id is not None:
            query = (
                query.join(bookmark_exercise_mapping)
                .join(Bookmark)
                .filter(Bookmark.user_id == user_id)
            )
        query = query.order_by("time")

        return query.all()

    def get_user_id(self):
        """
        Finds related user_id corresponding to the exercise

        returns: user_id or None when none is found
        """
        from zeeguu.core.model.bookmark import Bookmark
        import sqlalchemy

        query = Bookmark.query.filter(Bookmark.exercise_log.any(id=self.id))

        try:
            corresponding_bookmark = query.one()
            return corresponding_bookmark.user_id
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    def get_bookmark(self):
        from zeeguu.core.model.bookmark import Bookmark, bookmark_exercise_mapping

        q = (
            Bookmark.query.join(bookmark_exercise_mapping)
            .join(Exercise)
            .filter(Exercise.id == self.id)
        )
        return q.one()

    def is_too_easy(self):
        return self.outcome.outcome in ExerciseOutcome.too_easy_outcomes

    def is_correct(self):
        return self.outcome.outcome in ExerciseOutcome.correct_outcomes
