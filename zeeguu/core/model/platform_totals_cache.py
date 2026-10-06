import json
from datetime import datetime

from sqlalchemy import Column, Integer, Text, DateTime

from zeeguu.core.model.db import db


class PlatformTotalsCache(db.Model):
    """
    The last computed platform totals (see
    zeeguu.core.user_statistics.platform_totals), shared by all workers so
    that a restart does not make every one of them recompute. A single row.
    """

    __tablename__ = "platform_totals_cache"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    totals_json = Column(Text, nullable=False)
    computed_at = Column(DateTime, nullable=False)

    @property
    def totals(self):
        return json.loads(self.totals_json)

    @classmethod
    def latest(cls):
        return cls.query.order_by(cls.computed_at.desc()).first()

    @classmethod
    def store(cls, session, totals):
        entry = cls.latest() or cls()
        entry.totals_json = json.dumps(totals)
        entry.computed_at = datetime.now()
        session.add(entry)
        session.commit()
        return entry
