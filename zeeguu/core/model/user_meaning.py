from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import relationship

from zeeguu.core.model import db


class UserMeaning(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    learned_time = db.Column(db.DateTime)

    level = db.Column(db.Integer)

    exercise_log = relationship(
        Exercise, secondary="bookmark_exercise_mapping", order_by="Exercise.id"
    )

    def __init__(
        self,
        level: int = 0,
    ):
        self.level = level
        self.fit_for_study = fit_for_study(self)

    @classmethod
    def find_or_create(
        cls,
        session,
        _origin: str,
        _origin_lang: str,
        _translation: str,
        _translation_lang: str,
    ):
        from zeeguu.core.model import Phrase, Language

        origin_lang = Language.find_or_create(_origin_lang)
        translation_lang = Language.find_or_create(_translation_lang)

        origin = Phrase.find_or_create(session, _origin, origin_lang)
        session.add(origin)

        translation = Phrase.find_or_create(session, _translation, translation_lang)
        session.add(translation)

        try:
            meaning = cls.query.filter_by(origin=origin, translation=translation).one()
        except NoResultFound:
            meaning = cls(origin, translation)
            session.add(meaning)
            session.commit()

        return meaning
