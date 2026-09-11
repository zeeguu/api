from sqlalchemy import Column, Integer, String, Text, JSON, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.language import Language


class AudioLessonMeaning(db.Model):
    """
    Individual audio lesson for a specific meaning (word/phrase translation pair).
    MP3 files are stored on disk as meaning-{id}-{teacher_language_code}.mp3
    (see audio_file_path).
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

    # The regional variety of the language being learned that this row was voiced
    # in, as the ISO 3166-1 alpha-2 country. Part of the cache key, not decoration:
    # these rows are shared across ALL users, so without it whoever generated the
    # lesson first would decide which accent every other learner hears.
    #
    # Deliberately NOT user_language.dialect, and not named after it. This is that
    # dialect put through distinguishing_variety() -- the variety insofar as it
    # changes the voice -- so a learner whose dialect is the language's default
    # lands here as NULL and shares the rows generated before dialects existed.
    # 'PT' and 'NL' therefore never appear in this column; asking for them finds
    # nothing, and asking with NULL is what finds their lessons.
    variety = Column(String(2))

    duration_seconds = Column(Integer)

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
        difficulty_level=None,
        voice_config=None,
        duration_seconds=None,
        teacher_language=None,
        ai_generator=None,
        variety=None,
    ):
        self.meaning_id = meaning.id
        self.script = script
        self.difficulty_level = difficulty_level
        self.variety = variety
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
    def find(cls, meaning, teacher_language=None, *, variety):
        """
        Find a non-deprecated audio lesson for a meaning, teacher language and variety.

        `variety` is required and keyword-only: None is a real answer here
        ("voiced without a preference"), so a default would let a caller that has
        never heard of varieties ask the same question as a learner who asked for
        nothing, and quietly get somebody else's accent.

        `variety=None` matches only rows voiced without a variety, and does so
        through IS NULL rather than `= NULL`, which matches nothing in SQL. Getting
        that wrong would not raise -- it would quietly miss the cache and
        regenerate every lesson for every learner who expressed no preference.
        """
        query = cls.query.filter_by(meaning=meaning).filter(cls.deprecated_at.is_(None))
        if teacher_language:
            query = query.filter_by(teacher_language_id=teacher_language.id)
        query = query.filter(
            cls.variety == variety if variety else cls.variety.is_(None)
        )
        return query.first()
