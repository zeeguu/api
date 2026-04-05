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

    canonical_suggestion = Column(String(100), nullable=False)
    lesson_type = Column(String(20), nullable=False)  # "topic" or "situation"
    title = Column(String(200), nullable=True)  # specific description, e.g. "ordering pizza at a trattoria"

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
        canonical_suggestion,
        lesson_type,
        language,
        difficulty_level=None,
        voice_config=None,
        duration_seconds=None,
        teacher_language=None,
        is_general=False,
        title=None,
    ):
        self.script = script
        self.created_by = created_by
        self.canonical_suggestion = canonical_suggestion
        self.lesson_type = lesson_type
        self.title = title
        self.language_id = language.id
        self.difficulty_level = difficulty_level
        self.voice_config = voice_config
        self.duration_seconds = duration_seconds
        self.is_general = is_general
        if teacher_language:
            self.teacher_language_id = teacher_language.id

    def __repr__(self):
        return f"<AudioLessonDialogue {self.id} '{self.canonical_suggestion}' ({self.lesson_type})>"

    @property
    def audio_file_path(self):
        lang_code = self.teacher_language.code if self.teacher_language else "en"
        return f"/audio/lessons/dialogue-{self.id}-{lang_code}.mp3"

    @classmethod
    def past_titles_for(cls, canonical_suggestion, lesson_type, language, teacher_language, difficulty_level):
        """Get all existing titles for this topic combination."""
        results = cls.query.filter_by(
            canonical_suggestion=canonical_suggestion,
            lesson_type=lesson_type,
            language_id=language.id,
            teacher_language_id=teacher_language.id,
            difficulty_level=difficulty_level,
        ).filter(cls.title.isnot(None)).with_entities(cls.title).all()
        return [r.title for r in results]

    @classmethod
    def find_unheard(cls, canonical_suggestion, lesson_type, language, teacher_language, difficulty_level, user):
        """
        Find an existing dialogue the user hasn't heard yet.
        Returns None if all matching dialogues have been heard (or none exist).
        """
        from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
        from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson

        # IDs of dialogues this user has already been served
        heard_ids = (
            db.session.query(DailyAudioLessonSegment.audio_lesson_dialogue_id)
            .join(DailyAudioLesson, DailyAudioLessonSegment.daily_audio_lesson_id == DailyAudioLesson.id)
            .filter(
                DailyAudioLesson.user_id == user.id,
                DailyAudioLessonSegment.audio_lesson_dialogue_id.isnot(None),
            )
        )

        query = cls.query.filter_by(
            canonical_suggestion=canonical_suggestion,
            lesson_type=lesson_type,
            language_id=language.id,
            teacher_language_id=teacher_language.id,
            difficulty_level=difficulty_level,
        ).filter(
            cls.id.notin_(heard_ids)
        )

        return query.first()
