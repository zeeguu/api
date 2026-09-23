import json

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UnicodeText, UniqueConstraint, func

from zeeguu.core.model.db import db


class PublicTranslation(db.Model):
    """Cached translation of one word position in an article, for the
    account-less shared-article page.

    The public page never sends text to translate -- only a position (which
    part of the article, paragraph, sentence, token span) -- and the server
    reads the word and its sentence from the stored article. So every answer
    here is keyed by position and is paid for once: the next visitor tapping
    the same word in the same shared article gets it from this table.

    ``part`` is "title" or the ArticleFragment id. ``partner_token_i`` is the
    other half of a separated MWE ("ruft ... an"), -1 when there is none (not
    NULL, so the unique key actually deduplicates).
    """

    __tablename__ = "public_translation"
    __table_args__ = (
        UniqueConstraint(
            "article_id", "part", "paragraph_i", "sent_i", "token_i", "total_tokens",
            "partner_token_i", "to_language_id",
            name="uq_public_translation_position",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # A cache must not keep an article alive: cascade with it on pruning.
    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), nullable=False)
    part = Column(String(32), nullable=False)
    paragraph_i = Column(Integer, nullable=False)
    sent_i = Column(Integer, nullable=False)
    token_i = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    partner_token_i = Column(Integer, nullable=False, default=-1)
    to_language_id = Column(Integer, ForeignKey("language.id"), nullable=False)
    translation = Column(UnicodeText, nullable=False)
    source = Column(String(255))
    # The 3-way voter's full list ([{translation, source, votes}, ...]), kept so
    # the page can later show the other translators' answers at no extra cost.
    alternatives_json = Column(UnicodeText)
    created_at = Column(DateTime, default=func.now())

    @classmethod
    def find(cls, article_id, position, to_language_id):
        return cls.query.filter_by(article_id=article_id, to_language_id=to_language_id, **position).first()

    @classmethod
    def store(cls, session, article_id, position, to_language_id, result):
        row = cls(
            article_id=article_id,
            to_language_id=to_language_id,
            translation=result["translation"],
            source=result.get("source"),
            alternatives_json=json.dumps(result["alternatives"]) if result.get("alternatives") else None,
            **position,
        )
        # Two visitors tapping the same word at once race the unique key; the
        # loser just doesn't cache (the winner's row serves the next tap).
        try:
            with session.begin_nested():
                session.add(row)
        except Exception:
            pass
        return row

    def as_response(self):
        return {
            "translation": self.translation,
            "source": self.source,
            "alternatives": json.loads(self.alternatives_json) if self.alternatives_json else None,
        }
