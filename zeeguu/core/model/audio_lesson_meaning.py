from sqlalchemy import Column, Integer, String, Text, JSON, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.language import Language


class AudioLessonMeaning(db.Model):
    """
    Individual audio lesson for a specific meaning (word/phrase translation pair).
    MP3 files are stored on disk with filename pattern: {meaning_id}-{language_code}.mp3
    """

    __tablename__ = "audio_lesson_meaning"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)

    meaning_id = Column(
        Integer, ForeignKey(Meaning.id, ondelete="CASCADE"), nullable=False
    )
    meaning = relationship(Meaning, backref="audio_lessons")

    script = Column(Text, nullable=False)
    voice_config = Column(JSON)

    teacher_language_id = Column(Integer, ForeignKey(Language.id), nullable=True)
    teacher_language = relationship(Language)

    difficulty_level = Column(
        Enum("A1", "A2", "B1", "B2", "C1", "C2", name="cefr_level")
    )
    duration_seconds = Column(Integer)
    # Superseded by ai_generator_id, which names the model that actually answered
    # and the prompt version that produced this script. Kept nullable and no longer
    # written: every existing row says the literal 'claude-v1', including the ones
    # DeepSeek wrote while the Anthropic cap was reached. Dropped once no deployed
    # code selects it.
    created_by = Column(String(255), nullable=True)

    # Which model and prompt version actually produced this script. created_by is a
    # fixed literal and cannot answer that: the fallback chain may serve from a
    # different provider than the configured one, so it has to be recorded here.
    ai_generator_id = Column(Integer, ForeignKey(AIGenerator.id), nullable=True)
    ai_generator = relationship(AIGenerator)  # e.g. Claude-v2-Opus-Promopt1

    # When set, cache lookups skip this row and force regeneration. Existing
    # daily lesson segments that already reference it keep playing as before.
    deprecated_at = Column(DateTime, nullable=True)

    def __init__(
        self,
        meaning,
        script,
        created_by=None,
        difficulty_level=None,
        voice_config=None,
        duration_seconds=None,
        teacher_language=None,
        ai_generator=None,
    ):
        self.meaning_id = meaning.id
        self.script = script
        self.created_by = created_by
        self.difficulty_level = difficulty_level
        self.voice_config = voice_config
        self.duration_seconds = duration_seconds
        if teacher_language:
            self.teacher_language_id = teacher_language.id
        if ai_generator:
            self.ai_generator_id = ai_generator.id

    def __repr__(self):
        return f"<AudioLessonMeaning {self.id} for meaning {self.meaning_id}>"

    @property
    def audio_file_path(self):
        """Path for the audio file, keyed on the AudioLessonMeaning row id so distinct rows for the same meaning (e.g. one deprecated, one regenerated) don't overwrite each other on disk."""
        lang_code = self.teacher_language.code if self.teacher_language else "en"
        return f"/audio/lessons/meaning-{self.id}-{lang_code}.mp3"

    @classmethod
    def find(cls, meaning, teacher_language=None):
        """Find a non-deprecated audio lesson for a specific meaning and teacher language."""
        query = cls.query.filter_by(meaning=meaning).filter(cls.deprecated_at.is_(None))
        if teacher_language:
            query = query.filter_by(teacher_language_id=teacher_language.id)
        return query.first()
