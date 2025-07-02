from sqlalchemy import Column, Integer, String, Text, Enum

from zeeguu.core.model.db import db


class DailyAudioLessonWrapper(db.Model):
    """
    Wrapper scripts (intro/outro) for daily audio lessons.
    MP3 files are stored on disk with filename pattern: {id}.mp3
    """
    
    __tablename__ = 'daily_audio_lesson_wrapper'
    __table_args__ = {'mysql_collate': 'utf8mb4_unicode_ci'}

    id = Column(Integer, primary_key=True)
    
    script = Column(Text, nullable=False)
    wrapper_type = Column(Enum('intro', 'outro', name='wrapper_type'), nullable=False)
    duration_seconds = Column(Integer)
    created_by = Column(String(255), nullable=False)

    def __init__(self, script, wrapper_type, created_by, duration_seconds=None):
        self.script = script
        self.wrapper_type = wrapper_type
        self.created_by = created_by
        self.duration_seconds = duration_seconds

    def __repr__(self):
        return f'<DailyAudioLessonWrapper {self.id}: {self.wrapper_type}>'

    @property
    def audio_file_path(self):
        """Returns the expected path for the audio file based on wrapper ID"""
        return f"/audio/wrappers/{self.id}.mp3"

    @classmethod
    def create_intro(cls, script, created_by):
        """Create an intro wrapper"""
        return cls(script=script, wrapper_type='intro', created_by=created_by)

    @classmethod
    def create_outro(cls, script, created_by):
        """Create an outro wrapper"""
        return cls(script=script, wrapper_type='outro', created_by=created_by)