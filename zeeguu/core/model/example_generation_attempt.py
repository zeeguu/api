from datetime import timedelta

import sqlalchemy

from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.util.time import server_now


class ExampleGenerationAttempt(db.Model):
    """
    A (meaning, level) the nightly prefetch wrote examples for and still fell
    short of the examples it needs: the LLM's sentences could not be anchored
    (separable verbs like "schreibt darüber", multi-word expressions), or the
    validator rejected them.

    Without this the prefetch asks the LLM again every night. With it, the
    pair pauses: a week after the first short try, a month after the second,
    and for good after the third, until the example prompt changes. A side
    table rather than a column on meaning: few meanings land here, and the
    rows are also the list of what the generator cannot handle.
    """

    __tablename__ = "example_generation_attempt"
    __table_args__ = (
        sqlalchemy.UniqueConstraint("meaning_id", "cefr_level"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"},
    )

    # A pause per number of short tries so far; past the list, for good
    PAUSES = [timedelta(days=7), timedelta(days=30)]

    id = db.Column(db.Integer, primary_key=True)
    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id, ondelete="CASCADE"), nullable=False)
    cefr_level = db.Column(db.String(2), nullable=False)
    # The example prompt the tries were made with; a new one starts over
    prompt_version = db.Column(db.String(32), nullable=False)
    short_tries = db.Column(db.Integer, nullable=False, default=0)
    last_try_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def record_short_try(cls, session, meaning_id, cefr_level, prompt_version, now=None):
        now = now or server_now()
        row = cls.query.filter_by(meaning_id=meaning_id, cefr_level=cefr_level).first()
        if row is None:
            row = cls(meaning_id=meaning_id, cefr_level=cefr_level, prompt_version=prompt_version, short_tries=0)
        if row.prompt_version != prompt_version:
            row.prompt_version = prompt_version
            row.short_tries = 0
        row.short_tries += 1
        row.last_try_at = now
        session.add(row)

    def is_paused(self, prompt_version, now):
        if self.prompt_version != prompt_version:
            return False
        if self.short_tries > len(self.PAUSES):
            return True
        return now < self.last_try_at + self.PAUSES[self.short_tries - 1]

    @classmethod
    def paused_meaning_ids(cls, meaning_ids, cefr_level, prompt_version, now=None):
        """Of these meanings, those whose examples at `cefr_level` are on pause."""
        if not meaning_ids:
            return set()
        now = now or server_now()
        rows = cls.query.filter(cls.meaning_id.in_(meaning_ids), cls.cefr_level == cefr_level).all()
        return {row.meaning_id for row in rows if row.is_paused(prompt_version, now)}
