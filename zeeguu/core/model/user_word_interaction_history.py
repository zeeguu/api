from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.user_word import UserWord


class UserWordInteractionHistory(db.Model):
    __tablename__ = "user_word_interaction_history"

    id = Column(Integer, primary_key=True)

    user_word_id = Column(Integer, ForeignKey(UserWord.id), nullable=False)
    user_word = relationship(UserWord)

    interaction_type = Column(String(50), nullable=False)
    event_time = Column(DateTime, nullable=False, default=datetime.now)

    # Interaction type constants
    TRANSLATED = "translated"
    DECLARED_KNOWN = "declared_known"
    BAD_TRANSLATION = "bad_translation"
    MANUAL_ADDITION = "manual_addition"

    def __init__(self, user_word, interaction_type):
        self.user_word = user_word
        self.interaction_type = interaction_type
        self.event_time = datetime.now()

    @classmethod
    def log(cls, session, user_word, interaction_type):
        entry = cls(user_word, interaction_type)
        session.add(entry)
