from sqlalchemy import Column, Integer, String, Text, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language


class AudioLessonDialogue(db.Model):
    """
    Audio lesson based on a single flowing dialogue about a topic or situation.
    The dialogue is about topic immersion — not centered on specific vocabulary words.
    User words may be sprinkled in as hints but are not tracked here.

    MP3 files are stored on disk: {ZEEGUU_DATA_FOLDER}/audio/dialogues/{id}-{lang_code}.mp3
    """

    __tablename__ = "audio_lesson_dialogue"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)

    script = Column(Text, nullable=False)
    voice_config = Column(JSON)

    suggestion = Column(String(100), nullable=False)
    suggestion_type = Column(String(20), nullable=False)  # "topic" or "situation"

    language_id = Column(Integer, ForeignKey(Language.id), nullable=False)
    language = relationship(Language, foreign_keys=[language_id])

    teacher_language_id = Column(Integer, ForeignKey(Language.id), nullable=True)
    teacher_language = relationship(Language, foreign_keys=[teacher_language_id])

    difficulty_level = Column(
        Enum("A1", "A2", "B1", "B2", "C1", "C2", name="cefr_level")
    )
    duration_seconds = Column(Integer)
    is_general = Column(db.Boolean, default=False)
    created_by = Column(String(255), nullable=False)

    def __init__(
        self,
        script,
        created_by,
        suggestion,
        suggestion_type,
        language,
        difficulty_level=None,
        voice_config=None,
        duration_seconds=None,
        teacher_language=None,
        is_general=False,
    ):
        self.script = script
        self.created_by = created_by
        self.suggestion = suggestion
        self.suggestion_type = suggestion_type
        self.language_id = language.id
        self.difficulty_level = difficulty_level
        self.voice_config = voice_config
        self.duration_seconds = duration_seconds
        self.is_general = is_general
        if teacher_language:
            self.teacher_language_id = teacher_language.id

    def __repr__(self):
        return f"<AudioLessonDialogue {self.id} '{self.suggestion}' ({self.suggestion_type})>"

    @property
    def audio_file_path(self):
        lang_code = self.teacher_language.code if self.teacher_language else "en"
        return f"/audio/dialogues/{self.id}-{lang_code}.mp3"

    @classmethod
    def find(cls, suggestion, suggestion_type, language, teacher_language=None, difficulty_level=None):
        """Find an existing dialogue matching suggestion, type, language, teacher language, and level."""
        query = cls.query.filter_by(
            suggestion=suggestion,
            suggestion_type=suggestion_type,
            language_id=language.id,
        )
        if teacher_language:
            query = query.filter_by(teacher_language_id=teacher_language.id)
        if difficulty_level:
            query = query.filter_by(difficulty_level=difficulty_level)
        return query.first()
