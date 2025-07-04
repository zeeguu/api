from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.model.daily_audio_lesson_wrapper import DailyAudioLessonWrapper


class DailyAudioLessonSegment(db.Model):
    """
    Segments within a daily audio lesson. Can be intro, meaning lesson, or outro.
    Maintains the order of segments within a daily lesson.
    """
    
    __tablename__ = 'daily_audio_lesson_segment'
    __table_args__ = {'mysql_collate': 'utf8mb4_unicode_ci'}

    id = Column(Integer, primary_key=True)
    
    daily_audio_lesson_id = Column(Integer, ForeignKey('daily_audio_lesson.id', ondelete='CASCADE'), nullable=False)
    daily_lesson = relationship('DailyAudioLesson', back_populates='segments')
    
    segment_type = Column(Enum('intro', 'meaning_lesson', 'outro', name='segment_type'), nullable=False, default='meaning_lesson')
    
    audio_lesson_meaning_id = Column(Integer, ForeignKey(AudioLessonMeaning.id, ondelete='CASCADE'))
    audio_lesson_meaning = relationship(AudioLessonMeaning)
    
    daily_audio_lesson_wrapper_id = Column(Integer, ForeignKey(DailyAudioLessonWrapper.id, ondelete='CASCADE'))
    daily_audio_lesson_wrapper = relationship(DailyAudioLessonWrapper)
    
    sequence_order = Column(Integer, nullable=False)

    def __init__(self, daily_lesson, segment_type='meaning_lesson', audio_lesson_meaning=None, daily_audio_lesson_wrapper=None, sequence_order=1):
        self.daily_lesson = daily_lesson
        self.segment_type = segment_type
        self.audio_lesson_meaning = audio_lesson_meaning
        self.daily_audio_lesson_wrapper = daily_audio_lesson_wrapper
        self.sequence_order = sequence_order

    def __repr__(self):
        return f'<DailyAudioLessonSegment {self.id}: {self.segment_type}, order={self.sequence_order}>'

    @property
    def audio_file_path(self):
        """Returns the expected path for the audio file based on segment type and content"""
        if self.segment_type == 'meaning_lesson' and self.audio_lesson_meaning:
            return self.audio_lesson_meaning.audio_file_path
        elif self.daily_audio_lesson_wrapper:
            return self.daily_audio_lesson_wrapper.audio_file_path
        else:
            return None

    @property
    def is_intro(self):
        return self.segment_type == 'intro'
    
    @property
    def is_outro(self):
        return self.segment_type == 'outro'
    
    @property
    def is_meaning_lesson(self):
        return self.segment_type == 'meaning_lesson'