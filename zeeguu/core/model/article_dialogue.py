"""
A short dialogue for absolute beginners (A0), written from an article and read
in the reader as a text of its own, "inspired by" that article.

The dialogue is an Article row, so translation, bookmarks and exercises work
on it as on any text. The reader shows an article as its fragments
(ArticleFragment, in order); a dialogue has one fragment per spoken line, and
ArticleDialogue.speakers says who speaks each, in the same order. The names
are kept out of the text so they never become words a learner can tap, find in
a bookmark's context, or hear read aloud.

It is linked to the article it comes from only here, never through
Article.parent_article_id, which the level switcher, on-demand simplification,
pruning and indexing all read as "a simplification of".

See docs/future-work/beginner-feed.md.
"""

import unicodedata
import uuid
from datetime import datetime
from html import escape

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.article import Article
from zeeguu.core.model.db import db
from zeeguu.core.model.source import Source
from zeeguu.core.model.source_type import SourceType
from zeeguu.core.tokenization.zeeguu_tokenizer import ZeeguuTokenizer

# The texts are written for A0 learners, but article.cefr_level has no A0:
# A1 is the lowest level a text can have (see cefr.readable).
DIALOGUE_CEFR_LEVEL = "A1"


class ArticleDialogue(db.Model):
    __tablename__ = "article_dialogue"
    __table_args__ = (
        Index("ix_article_dialogue_inspired_by", "inspired_by_article_id"),
        {"mysql_collate": "utf8mb4_bin"},
    )

    article_id = Column(Integer, ForeignKey(Article.id, ondelete="CASCADE"), primary_key=True)
    article = relationship(Article, foreign_keys=[article_id])

    inspired_by_article_id = Column(
        Integer, ForeignKey(Article.id, ondelete="RESTRICT"), nullable=False
    )
    inspired_by = relationship(Article, foreign_keys=[inspired_by_article_id])

    # Who says each fragment of the dialogue article (one per line), in order.
    speakers = Column(JSON, nullable=False)

    writer_ai_generator_id = Column(Integer, ForeignKey(AIGenerator.id))
    writer_ai_generator = relationship(AIGenerator, foreign_keys=[writer_ai_generator_id])
    checker_ai_generator_id = Column(Integer, ForeignKey(AIGenerator.id))
    checker_ai_generator = relationship(AIGenerator, foreign_keys=[checker_ai_generator_id])

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    @classmethod
    def create(cls, session, inspired_by, title, lines, writer, checker):
        """
        The dialogue article and its row, added to `session` (not committed).

        `lines` is a list of (speaker, text). `writer` and `checker` are
        (model name, prompt version) pairs. Each line becomes one fragment,
        and one paragraph of the content. Raises ValueError for a line that
        would not stay one paragraph, since the speakers would then name the
        wrong lines.
        """
        lines = [(speaker.strip(), _nfc(text.strip())) for speaker, text in lines]
        if not lines or any(not speaker or not text or "\n" in text for speaker, text in lines):
            raise ValueError("Every line needs a speaker and a text on one line")
        content = "\n\n".join(text for _, text in lines)
        if len(ZeeguuTokenizer.split_into_paragraphs(content)) != len(lines):
            raise ValueError("The lines do not split into one paragraph each")

        language = inspired_by.language
        source = Source.find_or_create(
            session,
            content,
            SourceType.find_by_type(SourceType.ARTICLE),
            language,
            0,
            commit=False,
        )
        from zeeguu.core.model.url import Url

        article = Article(
            Url.find_or_create(session, f"https://zeeguu.org/dialogue/{uuid.uuid4()}"),
            _nfc(title.strip()),
            "",
            source,
            None,
            # The inspiring article's time, not now: the feed's fallback query
            # (when Elasticsearch is down) shows the newest articles to everyone.
            inspired_by.published_time,
            None,
            language,
            "".join(f"<p>{escape(text)}</p>" for _, text in lines),
            img_url=inspired_by.img_url,
        )
        article.cefr_level = DIALOGUE_CEFR_LEVEL
        session.add(article)
        session.flush()

        # Made here, one per line, rather than parsed from the HTML by
        # create_article_fragments: speakers[i] belongs to fragment i.
        from zeeguu.core.model.article_fragment import ArticleFragment

        for order, (_, text) in enumerate(lines):
            ArticleFragment.find_or_create(session, article, text, order, "p", commit=False)

        dialogue = cls(
            article_id=article.id,
            inspired_by_article_id=inspired_by.id,
            speakers=[speaker for speaker, _ in lines],
            writer_ai_generator=AIGenerator.find_or_create(session, *writer),
            checker_ai_generator=AIGenerator.find_or_create(session, *checker),
        )
        session.add(dialogue)
        return dialogue

    @classmethod
    def find(cls, article_id):
        return cls.query.filter_by(article_id=article_id).one_or_none()

    @classmethod
    def article_ids_inspired_by(cls, article_ids):
        """{inspiring article id: dialogue article id} for those that have one."""
        if not article_ids:
            return {}
        rows = cls.query.with_entities(cls.inspired_by_article_id, cls.article_id).filter(
            cls.inspired_by_article_id.in_(list(article_ids))
        )
        return dict(rows.all())

    def info(self):
        """What the reader needs to show the dialogue: who says each fragment,
        and the article it is inspired by."""
        return {
            "speakers": self.speakers,
            "inspired_by": {
                "id": self.inspired_by.id,
                "title": self.inspired_by.title,
                "url": self.inspired_by.url.as_string() if self.inspired_by.url else None,
            },
        }


def _nfc(text):
    # LLMs sometimes return decomposed letters (NFD), which render badly.
    return unicodedata.normalize("NFC", text) if text else text
