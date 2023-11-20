from sqlalchemy.orm.exc import NoResultFound

import zeeguu.core

from zeeguu.core.model import db


class ExerciseSource(db.Model):
    __tablename__ = "exercise_source"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(255), nullable=False)

    TOP_BOOKMARKS_MINI_EXERCISE = "Top Bookmarks Mini-Exercise"

    def __init__(self, source):
        self.source = source

    def __eq__(self, other):
        return self.id == other.id and self.source == other.source

    @classmethod
    def find(cls, source):
        return cls.query.filter_by(source=source).one()

    @classmethod
    def find_or_create(cls, session, _source):
        try:
            source = cls.find(_source)

        except NoResultFound as e:
            source = cls(_source)
        except Exception as e:
            raise e

        session.add(source)
        session.commit()

        return source
