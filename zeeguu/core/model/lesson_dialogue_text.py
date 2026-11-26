"""
The dialogue of an audio lesson, as a text a learner reads line by line.

A Source of its own type (LessonDialogue), like a ShortText: taps carry its
source_id and the LessonDialogue context type, so a reopened dialogue shows the
words tapped before, and the bookmarks go to exercises like any other. One
paragraph per spoken line; `speakers` says who says each, in the same order,
so the speakers never become words of the text.

Made the first time a learner asks to read the dialogue, then shared by
everyone who heard that lesson.
"""

import json
import unicodedata
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import relationship

from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_text import SourceText
from zeeguu.core.model.source_type import SourceType


class LessonDialogueText(db.Model):
    __tablename__ = "lesson_dialogue_text"
    __table_args__ = {"mysql_collate": "utf8mb4_bin"}

    id = Column(Integer, primary_key=True)

    source_id = Column(Integer, ForeignKey(Source.id), nullable=False, unique=True)
    source = relationship(Source)

    audio_lesson_dialogue_id = Column(
        Integer,
        ForeignKey(AudioLessonDialogue.id, ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    audio_lesson_dialogue = relationship(AudioLessonDialogue)

    # Who says each line ("Man", "Woman"), in order.
    speakers = Column(JSON, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # The reader's tokens as JSON, computed on the first read (see tokens).
    tokenized_paragraphs = Column(UnicodeText)

    @property
    def content(self):
        return self.source.get_content()

    @property
    def language(self):
        return self.source.language

    def tokens(self, session, tokenize):
        """The cached tokens, computed with `tokenize(content, language)` the first time."""
        if self.tokenized_paragraphs is None:
            self.tokenized_paragraphs = json.dumps(tokenize(self.content, self.language))
            session.add(self)
        return json.loads(self.tokenized_paragraphs)

    @classmethod
    def find_or_create(cls, session, lesson_dialogue, lines):
        """
        The text of `lesson_dialogue`, made from `lines` (DialogueLine, see
        script_parser.dialogue_lines) if there is none yet. Not committed.

        The content has one line per spoken line, which the reader's tokenizer
        reads as one paragraph each. Raises ValueError for a line that is empty
        or has a line break in it, since the speakers would then name the
        wrong lines.
        """
        texts = [_nfc(line.text.strip()) for line in lines]
        if not texts or any(not text or "\n" in text for text in texts):
            raise ValueError("Every line needs a text on one line")

        def make():
            # A Source per dialogue, never shared: source_id is unique here,
            # and two dialogues could have the same text.
            source = Source(
                SourceText.find_or_create(session, "\n".join(texts), commit=False),
                SourceType.find_by_type(SourceType.LESSON_DIALOGUE),
                lesson_dialogue.language,
            )
            session.add(source)
            session.flush()
            return cls(
                source_id=source.id,
                audio_lesson_dialogue_id=lesson_dialogue.id,
                speakers=[line.speaker for line in lines],
            )

        return find_or_create(
            session, cls, {"audio_lesson_dialogue_id": lesson_dialogue.id}, make
        )

    @classmethod
    def for_lesson_dialogue(cls, lesson_dialogue):
        return cls.query.filter_by(audio_lesson_dialogue_id=lesson_dialogue.id).one_or_none()


def _nfc(text):
    # LLMs sometimes return decomposed letters (NFD), which render badly.
    return unicodedata.normalize("NFC", text) if text else text
