import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.db import db


class ExerciseSource(db.Model):
    __tablename__ = "exercise_source"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(255), nullable=False)

    TOP_BOOKMARKS_MINI_EXERCISE = "Top Bookmarks Mini-Exercise"

    # Exercises where the learner produces the word in the language they learn:
    # types it, spells it, or says how it is said. The web's level-4 types
    # (web src/exercises/ExerciseTypeConstants.js); the level-3 ones translate
    # into the learner's own language, which is still recognition.
    PRODUCTION = frozenset(
        {
            "Cloze_L1_to_L2",
            "Spell_What_You_Hear",
            "Recall_L2W_from_L1W_no_hints",
            "Flashcard_L2W_from_L1W",
        }
    )

    def __init__(self, source):
        self.source = source

    def __eq__(self, other):
        return self.id == other.id and self.source == other.source

    @classmethod
    def find(cls, source):
        # .first() rather than .one(): source has no unique constraint in the
        # model, so concurrent first-seen inserts must not break future lookups
        # with MultipleResultsFound.
        found = cls.query.filter_by(source=source).order_by(cls.id.asc()).first()
        if found is None:
            raise NoResultFound()
        return found

    @classmethod
    def find_or_create(cls, session, _source):
        try:
            return cls.find(_source)
        except NoResultFound:
            try:
                source = cls(_source)
                session.add(source)
                session.commit()
                return source
            except sqlalchemy.exc.IntegrityError:
                session.rollback()
                return cls.find(_source)
