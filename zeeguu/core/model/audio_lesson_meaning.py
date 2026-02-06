from sqlalchemy import Column, Integer, String, Text, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.language import Language


class AudioLessonMeaning(db.Model):
    """
    Individual audio lesson for a specific meaning (word/phrase translation pair).
    MP3 files are stored on disk with filename pattern: {id}.mp3
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
    lesson_type = Column(String(50), default="contextual_examples")
    duration_seconds = Column(Integer)
    created_by = Column(String(255), nullable=False)  # e.g. Claude-v2-Opus-Promopt1

    def __init__(
        self,
        meaning,
        script,
        created_by,
        difficulty_level=None,
        lesson_type="contextual_examples",
        voice_config=None,
        duration_seconds=None,
        teacher_language=None,
    ):
        self.meaning = meaning
        self.script = script
        self.created_by = created_by
        self.difficulty_level = difficulty_level
        self.lesson_type = lesson_type
        self.voice_config = voice_config
        self.duration_seconds = duration_seconds
        if teacher_language:
            self.teacher_language_id = teacher_language.id

    def __repr__(self):
        return f"<AudioLessonMeaning {self.id} for meaning {self.meaning_id}>"

    @property
    def audio_file_path(self):
        """Returns the expected path for the audio file based on lesson ID"""
        return f"/audio/lessons/{self.id}.mp3"

    @classmethod
    def find(cls, meaning, teacher_language=None):
        """Find audio lesson for a specific meaning and teacher language"""
        query = cls.query.filter_by(meaning=meaning)
        if teacher_language:
            query = query.filter_by(teacher_language_id=teacher_language.id)
        return query.first()
