from datetime import timedelta

import sqlalchemy

from zeeguu.core.model.ai_generator import AIGenerator
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
    third, until the generator (LLM model or example prompt) changes. Once
    the meaning has enough examples, its row goes (the prefetch's
    forget_tries_of_covered_meanings), so a later shortfall starts at a week
    again.

    The generator is the one the prefetch means to use (its primary model and
    the current prompt), not whichever answered: a night on the fallback
    model does not start the pause over, a better primary model does.

    A side table rather than a column on meaning: few meanings land here,
    and its rows are also the list of what the generator cannot handle.
    """

    __tablename__ = "example_generation_attempt"
    __table_args__ = (
        # Named as in the migration, so metadata and the database agree
        sqlalchemy.UniqueConstraint("meaning_id", "cefr_level", name="meaning_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"},
    )

    # The pause after each try so far; past the list, for good
    PAUSES = [timedelta(days=7), timedelta(days=30)]

    id = db.Column(db.Integer, primary_key=True)
    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id, ondelete="CASCADE"), nullable=False)
    cefr_level = db.Column(db.String(2), nullable=False)
    # The generator the tries were made with; a new model or prompt starts over.
    # Compared by model and prompt, not id: ai_generator can hold duplicates.
    ai_generator_id = db.Column(db.Integer, db.ForeignKey(AIGenerator.id), nullable=False)
    ai_generator = db.relationship(AIGenerator, lazy="joined")
    tries = db.Column(db.Integer, nullable=False, default=0)
    last_try_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def record_try(cls, session, meaning_id, cefr_level, ai_generator, now=None):
        now = now or server_now()
        row = session.query(cls).filter_by(meaning_id=meaning_id, cefr_level=cefr_level).first()
        if row is None:
            row = cls(meaning_id=meaning_id, cefr_level=cefr_level, ai_generator=ai_generator, tries=0)
        if row.generator_key() != _key(ai_generator):
            row.ai_generator = ai_generator
            row.tries = 0
        row.tries += 1
        row.last_try_at = now
        session.add(row)

    def generator_key(self):
        return _key(self.ai_generator)

    def is_paused(self, generator_key, now):
        """`generator_key`: (model name, prompt version) of the generator the
        prefetch means to use now."""
        if self.generator_key() != generator_key or self.tries < 1:
            return False
        if self.tries > len(self.PAUSES):
            return True
        return now < self.last_try_at + self.PAUSES[self.tries - 1]

    @classmethod
    def paused_meaning_ids(cls, meaning_ids, cefr_level, generator_key, now=None):
        """Of these meanings, those whose examples at `cefr_level` are on pause."""
        if not meaning_ids:
            return set()
        now = now or server_now()
        rows = (
            db.session.query(cls)
            .filter(cls.meaning_id.in_(meaning_ids), cls.cefr_level == cefr_level)
            .all()
        )
        return {row.meaning_id for row in rows if row.is_paused(generator_key, now)}

    @classmethod
    def all_rows(cls, session):
        """Every row: few meanings ever land here."""
        return session.query(cls).all()


def _key(ai_generator):
    return (ai_generator.model_name, ai_generator.prompt_version)
