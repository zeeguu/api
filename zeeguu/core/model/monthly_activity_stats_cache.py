from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.db import db


class MonthlyActivityStatsCache(db.Model):
    """
    Cache for monthly activity statistics by type.
    Historical months are cached permanently.
    Current month is refreshed periodically.
    """

    __tablename__ = "monthly_activity_stats_cache"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    year_month = Column(String(7), unique=True, nullable=False)  # e.g., "2026-01"
    exercise_minutes = Column(Integer, nullable=False, default=0)
    reading_minutes = Column(Integer, nullable=False, default=0)
    browsing_minutes = Column(Integer, nullable=False, default=0)
    audio_minutes = Column(Integer, nullable=False, default=0)
    computed_at = Column(DateTime, nullable=False)

    def __init__(self, year_month, exercise_minutes, reading_minutes, browsing_minutes, audio_minutes):
        self.year_month = year_month
        self.exercise_minutes = exercise_minutes
        self.reading_minutes = reading_minutes
        self.browsing_minutes = browsing_minutes
        self.audio_minutes = audio_minutes
        self.computed_at = datetime.now()

    @classmethod
    def get_cached(cls, year_month):
        """Get cached stats for a month, or None if not cached."""
        try:
            return cls.query.filter_by(year_month=year_month).one()
        except NoResultFound:
            return None

    @classmethod
    def set_cached(cls, session, year_month, exercise_minutes, reading_minutes, browsing_minutes, audio_minutes):
        """Set or update cached stats for a month."""
        existing = cls.get_cached(year_month)
        if existing:
            existing.exercise_minutes = exercise_minutes
            existing.reading_minutes = reading_minutes
            existing.browsing_minutes = browsing_minutes
            existing.audio_minutes = audio_minutes
            existing.computed_at = datetime.now()
        else:
            new_entry = cls(year_month, exercise_minutes, reading_minutes, browsing_minutes, audio_minutes)
            session.add(new_entry)
        session.commit()

    @classmethod
    def get_all_cached(cls):
        """Get all cached months as a dict {year_month: cache_entry}."""
        entries = cls.query.all()
        return {e.year_month: e for e in entries}
