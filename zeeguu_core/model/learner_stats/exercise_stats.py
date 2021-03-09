import sqlalchemy

import zeeguu_core
from zeeguu_core.model.exercise_source import ExerciseSource

db = zeeguu_core.db


class ExerciseStats(db.Model):

    __tablename__ = 'algo_stats'
    __table_args__ = {'mysql_collate': 'utf8_bin'}

    exercise_source_id = db.Column(db.Integer, db.ForeignKey("exercise_source.id"), primary_key=True)
    exercise_source = db.relationship(ExerciseSource)

    mean = db.Column(db.DECIMAL(10, 3, asdecimal=False), nullable=False)
    sd = db.Column(db.DECIMAL(10, 3, asdecimal=False), nullable=False)

    updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    db.CheckConstraint('mean>=0', 'sd>=0')

    def __init__(self, exercise_source, mean, sd):
        self.exercise_source = exercise_source
        self.mean = mean
        self.sd = sd

    @classmethod
    def find(cls, exercise_stats):
        return cls.query.filter_by(exercise_source_id=exercise_stats.exercise_source.id).one()

    @classmethod
    def find_or_create(cls, session, exercise_stats):
        try:
            entry = cls.find(exercise_stats)

        except sqlalchemy.orm.exc.NoResultFound as e:
            entry = cls(exercise_stats.exercise_source, exercise_stats.mean, exercise_stats.sd)
        except Exception as e:
            raise e

        session.add(entry)
        session.commit()

        return entry
