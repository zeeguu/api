"""
Test fixtures for core model tests.

These set up required database records like context types and source types.
"""
from zeeguu.core.model.db import db

db_session = db.session


def add_context_types():
    """Add all context types to the database."""
    from zeeguu.core.model.context_type import ContextType

    for type in ContextType.ALL_TYPES:
        ContextType.find_or_create(db_session, type, commit=False)
    db_session.commit()


def add_source_types():
    """Add all source types to the database."""
    from zeeguu.core.model.source_type import SourceType

    for type in SourceType.ALL_TYPES:
        SourceType.find_or_create(db_session, type, commit=False)
    db_session.commit()
