from datetime import timedelta

import sqlalchemy

from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.util.time import server_now


class ExampleGenerationAttempt(db.Model):
    """
    How often the nightly prefetch wrote examples for a (meaning, level) since
    that meaning was last seen with enough usable examples at that level.

    A meaning that is short again after a generation stayed short for a
    reason another night will not fix: the LLM's sentences could not be
    anchored (separable verbs like "schreibt darüber", multi-word
    expressions), or the validator later rejected them. Without this the
    prefetch asks the LLM again every night. With it, the pair pauses: a week
    after the first try, a month after the second, and for good after the
    third, until the example prompt changes. Once the meaning is seen with
    enough examples, its row goes (clear_covered), so a later shortfall
    starts at a week again.

    A side table rather than a column on meaning: few meanings land here,
    and its rows are also the list of what the generator cannot handle.
    """

    __tablename__ = "example_generation_attempt"
    __table_args__ = (
        sqlalchemy.UniqueConstraint("meaning_id", "cefr_level"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"},
    )

    # The pause after each try so far; past the list, for good
    PAUSES = [timedelta(days=7), timedelta(days=30)]

    id = db.Column(db.Integer, primary_key=True)
    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id, ondelete="CASCADE"), nullable=False)
    cefr_level = db.Column(db.String(2), nullable=False)
    # The example prompt the tries were made with; a new one starts over
    prompt_version = db.Column(db.String(32), nullable=False)
    tries = db.Column(db.Integer, nullable=False, default=0)
    last_try_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def record_try(cls, session, meaning_id, cefr_level, prompt_version, now=None):
        now = now or server_now()
        row = cls.query.filter_by(meaning_id=meaning_id, cefr_level=cefr_level).first()
        if row is None:
            row = cls(meaning_id=meaning_id, cefr_level=cefr_level, prompt_version=prompt_version, tries=0)
        if row.prompt_version != prompt_version:
            row.prompt_version = prompt_version
            row.tries = 0
        row.tries += 1
        row.last_try_at = now
        session.add(row)

    def is_paused(self, prompt_version, now):
        if self.prompt_version != prompt_version or self.tries < 1:
            return False
        if self.tries > len(self.PAUSES):
            return True
        return now < self.last_try_at + self.PAUSES[self.tries - 1]

    @classmethod
    def paused_meaning_ids(cls, meaning_ids, cefr_level, prompt_version, now=None):
        """Of these meanings, those whose examples at `cefr_level` are on pause."""
        if not meaning_ids:
            return set()
        now = now or server_now()
        rows = cls.query.filter(cls.meaning_id.in_(meaning_ids), cls.cefr_level == cefr_level).all()
        return {row.meaning_id for row in rows if row.is_paused(prompt_version, now)}

    @classmethod
    def clear_covered(cls, session, meaning_ids, cefr_level):
        """These meanings have enough examples at `cefr_level` now: forget
        their tries, so a later shortfall pauses for a week, not longer."""
        if not meaning_ids:
            return
        cls.query.filter(cls.meaning_id.in_(meaning_ids), cls.cefr_level == cefr_level).delete(
            synchronize_session=False
        )
