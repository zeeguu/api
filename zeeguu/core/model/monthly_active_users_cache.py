from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.db import db


class MonthlyActiveUsersCache(db.Model):
    """
    Cache for monthly active user counts.
    Historical months are cached permanently.
    Current month is refreshed periodically.
    """

    __tablename__ = "monthly_active_users_cache"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)
    year_month = Column(String(7), unique=True, nullable=False)  # e.g., "2026-01"
    active_users = Column(Integer, nullable=False)
    computed_at = Column(DateTime, nullable=False)

    def __init__(self, year_month, active_users):
        self.year_month = year_month
        self.active_users = active_users
        self.computed_at = datetime.now()

    @classmethod
    def get_cached(cls, year_month):
        """Get cached count for a month, or None if not cached."""
        try:
            return cls.query.filter_by(year_month=year_month).one()
        except NoResultFound:
            return None

    @classmethod
    def set_cached(cls, session, year_month, active_users):
        """Set or update cached count for a month."""
        existing = cls.get_cached(year_month)
        if existing:
            existing.active_users = active_users
            existing.computed_at = datetime.now()
        else:
            new_entry = cls(year_month, active_users)
            session.add(new_entry)
        session.commit()

    @classmethod
    def get_all_cached(cls):
        """Get all cached months as a dict {year_month: active_users}."""
        entries = cls.query.all()
        return {e.year_month: e for e in entries}
