"""
Session-scoped test fixtures for core tests.

Creates the Flask app and schema once. Cleans per-test data between tests.
Mocks wordstats to avoid loading 400k WordInfo objects (~12s).
"""

import requests_mock

from zeeguu.core.test.test_app import create_test_app
from zeeguu.core.model.db import db as _db
from zeeguu.core.test.mocking_the_web import mock_requests_get


_app = None
_mock = None
_fixtures_initialized = False

# Tables whose data persists across tests (expensive to recreate)
_KEEP_TABLES = frozenset({
    "language",
    "context_type",
    "source_type",
})


class _FakeWordInfo:
    """Lightweight stand-in for wordstats.WordInfo / UnknownWordInfo."""
    def __init__(self, word):
        self.word = word
        self.frequency = 5.0
        self.importance = 5.0
        self.difficulty = 0.5
        self.klevel = 3
        self.rank = 1000


class _FakeLanguageInfo:
    """Returns a _FakeWordInfo for any word lookup."""
    def __getitem__(self, word):
        return _FakeWordInfo(word)

    def all_words(self):
        return []

    @property
    def word_info_dict(self):
        return {}


def _install_wordstats_mock():
    """
    Pre-populate wordstats caches so they never load from disk.
    Must be called before any code touches Word.stats() or lang_info().
    """
    from wordstats import Word
    from zeeguu.core import word_stats

    fake = _FakeLanguageInfo()

    # Mock Word.stats_dict for all languages tests use
    for lang in ("de", "en", "da", "es", "fr", "it", "pt", "nl", "el"):
        Word.stats_dict[lang] = fake
        word_stats.lang_cache[lang] = fake


def get_shared_app():
    """Return the session-scoped app for use by ModelTestMixIn."""
    global _app
    if _app is None:
        _install_wordstats_mock()
        _app = create_test_app()
    return _app


def get_mock():
    """Return the session-scoped request mock."""
    global _mock
    if _mock is None:
        _mock = requests_mock.Mocker()
        _mock.start()
        mock_requests_get(_mock)
    return _mock


def init_fixtures_once():
    """Initialize context_type and source_type once per session."""
    global _fixtures_initialized
    if _fixtures_initialized:
        return

    from zeeguu.core.test.fixtures import add_context_types, add_source_types
    add_context_types()
    add_source_types()
    _fixtures_initialized = True


def cleanup_tables():
    """Delete per-test data while keeping fixture tables."""
    _db.session.remove()
    for table in reversed(_db.metadata.sorted_tables):
        if table.name not in _KEEP_TABLES:
            _db.session.execute(table.delete())
    _db.session.commit()
