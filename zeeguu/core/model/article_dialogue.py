"""
The dialogue of an audio lesson, as a text a learner reads in the reader.

The dialogue is an Article row, so translation, bookmarks and exercises work
on it as on any text. The reader shows an article as its fragments
(ArticleFragment, in order); a dialogue has one fragment per spoken line, and
ArticleDialogue.speakers says who speaks each, in the same order. The speakers
are kept out of the text so they never become words a learner can tap, find in
a bookmark's context, or hear read aloud.

The article is made the first time a learner asks to read the dialogue, and
then shared by everyone who heard that lesson.
"""

import unicodedata
import uuid
from datetime import datetime
from html import escape

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from zeeguu.core.audio_lessons.script_parser import DialogueLine
from zeeguu.core.model.article import Article
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.tokenization.zeeguu_tokenizer import ZeeguuTokenizer


class ArticleDialogue(db.Model):
    __tablename__ = "article_dialogue"
    __table_args__ = {"mysql_collate": "utf8mb4_bin"}

    article_id = Column(Integer, ForeignKey(Article.id, ondelete="CASCADE"), primary_key=True)
    article = relationship(Article, foreign_keys=[article_id])

    audio_lesson_dialogue_id = Column(
        Integer,
        ForeignKey(AudioLessonDialogue.id, ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    audio_lesson_dialogue = relationship(AudioLessonDialogue)

    # Who says each fragment of the article (one per line), in order.
    speakers = Column(JSON, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    @classmethod
    def find_or_create(cls, session, lesson_dialogue, lines):
        """
        The dialogue article of `lesson_dialogue`, made from `lines` if there is
        none yet. Commits.

        `lines` is a list of DialogueLine, see script_parser.dialogue_lines.
        Raises ValueError for lines that would not stay one paragraph each,
        since the speakers would then name the wrong lines.
        """
        lines = [DialogueLine(line.speaker, _nfc(line.text.strip())) for line in lines]
        if not lines or any(not line.text or "\n" in line.text for line in lines):
            raise ValueError("Every line needs a text on one line")
        content = "\n\n".join(line.text for line in lines)
        if len(ZeeguuTokenizer.split_into_paragraphs(content)) != len(lines):
            raise ValueError("The lines do not split into one paragraph each")

        from zeeguu.core.model.url import Url

        # Made (and committed) before the savepoint below, as Url.find_or_create
        # commits. Random, not the lesson's id: an article left behind would
        # hold a url made from an id that the lesson table may give out again.
        # A request that loses the race below leaves its url unused.
        url = Url.find_or_create(session, f"https://zeeguu.org/dialogue/{uuid.uuid4()}")

        def make():
            return cls._make(session, lesson_dialogue, lines, content, url)

        dialogue = find_or_create(
            session, cls, {"audio_lesson_dialogue_id": lesson_dialogue.id}, make
        )
        session.commit()
        return dialogue

    @classmethod
    def _make(cls, session, lesson_dialogue, lines, content, url):
        language = lesson_dialogue.language
        source = Source.find_or_create(
            session,
            content,
            SourceType.find_by_type(SourceType.ARTICLE),
            language,
            0,
            commit=False,
        )
        article = Article(
            url,
            # In the learner's own language, as the lessons list shows it: so
            # not tokenized (Article.get_tokenized_content), shown as is.
            lesson_dialogue.title or lesson_dialogue.canonical_suggestion,
            "",
            source,
            None,
            datetime.utcnow(),
            None,
            language,
            "".join(f"<p>{escape(line.text)}</p>" for line in lines),
        )
        # article.cefr_level has no A0: A1 is the lowest level a text can have.
        level = lesson_dialogue.difficulty_level
        article.cefr_level = "A1" if level in (None, "A0") else level
        session.add(article)
        session.flush()

        # Made here, one per line, rather than parsed from the HTML by
        # create_article_fragments: speakers[i] belongs to fragment i.
        from zeeguu.core.model.article_fragment import ArticleFragment

        for order, line in enumerate(lines):
            ArticleFragment.find_or_create(session, article, line.text, order, "p", commit=False)

        return cls(
            article_id=article.id,
            audio_lesson_dialogue_id=lesson_dialogue.id,
            speakers=[line.speaker for line in lines],
        )

    @classmethod
    def find(cls, article_id):
        return cls.query.filter_by(article_id=article_id).one_or_none()

    def info(self):
        """What the reader needs to show the dialogue: who says each fragment.
        The title is in the learner's own language and comes untokenized."""
        return {"speakers": self.speakers}


def _nfc(text):
    # LLMs sometimes return decomposed letters (NFD), which render badly.
    return unicodedata.normalize("NFC", text) if text else text
