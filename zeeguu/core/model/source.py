from sqlalchemy import Column, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model.language import Language
from zeeguu.core.model.source_text import SourceText
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.model import db
from zeeguu.core.util import compute_fk_and_wordcount


class Source(db.Model):
    """Parent class that stores all the content types we have in the application
    (Article, Video, etc) so that we can refer to User Activity to the source rather
    than tracking multiple ids."""

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    source_text_id = Column(Integer, ForeignKey(SourceText.id))
    source_text = relationship(SourceText, foreign_keys="Source.source_text_id")

    source_type_id = Column(Integer, ForeignKey(SourceType.id))
    source_type = relationship(SourceType, foreign_keys="Source.source_type_id")

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    fk_difficulty = Column(Integer)
    word_count = Column(Integer)
    broken = Column(Integer)

    def __init__(self, source_text, source_type, language: Language, broken=0):
        self.source_text = source_text
        self.source_type = source_type
        self.language = language
        self.broken = broken

        self.fk_difficulty, self.word_count = compute_fk_and_wordcount(
            source_text.content, language
        )

    def get_content(self):
        return self.source_text.content

    @classmethod
    def find(cls, id: int):
        try:
            return cls.query.filter_by(id=id).order_by(cls.date.desc()).first()
        except NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        text,
        source_type,
        language: Language,
        broken,
        commit=True,
    ):
        source_text = SourceText.find_or_create(session, text, commit=commit)
        try:
            return cls.query.filter_by(
                source_text=source_text,
                source_type=source_type,
                language=language,
                broken=broken,
            ).one()

        except NoResultFound:
            new = cls(
                source_text,
                source_type,
                language,
                broken,
            )
            session.add(new)
            if commit:
                session.commit()
            return new
