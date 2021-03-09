import zeeguu_core

from zeeguu_core.model.exercise_outcome import ExerciseOutcome
from zeeguu_core.model.exercise_source import ExerciseSource

db = zeeguu_core.db


class Exercise(db.Model):
    __table_args__ = {'mysql_collate': 'utf8_bin'}
    __tablename__ = 'exercise'

    id = db.Column(db.Integer, primary_key=True)
    outcome_id = db.Column(db.Integer, db.ForeignKey(ExerciseOutcome.id), nullable=False)
    outcome = db.relationship(ExerciseOutcome)
    source_id = db.Column(db.Integer, db.ForeignKey(ExerciseSource.id), nullable=False)
    source = db.relationship(ExerciseSource)
    solving_speed = db.Column(db.Integer)
    time = db.Column(db.DateTime, nullable=False)

    def __init__(self, outcome, source, solving_speed, time):
        self.outcome = outcome
        self.source = source
        self.solving_speed = solving_speed
        self.time = time

    def short_string_summary(self):
        return str(self.source.id) + self.outcome.outcome[0]

    def __str__(self):
        return f'{self.source.source} ' + str(self.time) + f' {self.outcome.outcome}'

    def __repr__(self):
        return self.__str__()

    @classmethod
    def find(cls,
             user_id=None):
        """
            Find all the exercises for a particular or for all users 

            Parameters:
            user_id = user identifier

            return: list of exercises sorted by time in ascending order
        """
        from zeeguu_core.model.bookmark import Bookmark, bookmark_exercise_mapping

        query = cls.query
        if user_id is not None:
            query = query.join(bookmark_exercise_mapping).join(Bookmark).filter(Bookmark.user_id == user_id)
        query = query.order_by('time')

        return query.all()

    def find_user_id(self, db_session):
        """
            Finds related user_id corresponding to the exercise

            Parameters:
            db_session = database session

            returns: user_id or None when none is found
        """
        from zeeguu_core.model.bookmark import Bookmark, bookmark_exercise_mapping
        import sqlalchemy

        query = Bookmark.query.filter(Bookmark.exercise_log.any(id=self.id))

        try:
            corresponding_bookmark = query.one()
            return corresponding_bookmark.user_id
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    def get_bookmark(self):
        from zeeguu_core.model.bookmark import Bookmark, bookmark_exercise_mapping

        q = (Bookmark.query.
             join(bookmark_exercise_mapping).
             join(Exercise).
             filter(Exercise.id == self.id))
        return q.one()

    def is_too_easy(self):
        return self.outcome.outcome == ExerciseOutcome.TOO_EASY

    def is_correct(self):
        return self.outcome.outcome == ExerciseOutcome.CORRECT