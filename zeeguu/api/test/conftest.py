"""
Session-scoped test fixtures for fast API tests.

Instead of create_all/drop_all per test (~5s overhead each),
we create the schema once and load pre-computed article data from
a JSON fixture (skipping the ~25s Stanza NLP pipeline entirely).
"""

import pytest
import requests_mock

from zeeguu.api.app import create_app
from zeeguu.core.model.db import db as _db
from zeeguu.core.test.mocking_the_web import mock_requests_get


# Tables whose data persists across tests (expensive to recreate).
# Everything else gets wiped between tests.
_KEEP_TABLES = frozenset({
    "language",
    "context_type",
    "source_type",
    "domain_name",
    "url",
    "url_keyword",
    "source",
    "source_text",
    "article",
    "article_fragment",
    "article_cefr_assessment",
    "article_tokenization_cache",
    "article_url_keyword_map",
    "new_text",
})


@pytest.fixture(scope="session")
def app():
    """Create the Flask app, schema, and base data once for the entire session."""
    from zeeguu.core.test.conftest import _install_wordstats_mock
    _install_wordstats_mock()

    app = create_app(testing=True)

    with app.app_context():
        _db.create_all()

        # Load pre-computed article + NLP data from fixture file
        from zeeguu.core.test._session_data import load_session_fixture
        load_session_fixture()

    yield app

    with app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def db_cleanup(app):
    """
    Clean user-specific data between tests while keeping the schema
    and expensive base data (article, NLP fragments).
    """
    yield

    with app.app_context():
        _db.session.remove()

        # Only delete tables that contain per-test data
        for table in reversed(_db.metadata.sorted_tables):
            if table.name not in _KEEP_TABLES:
                _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture()
def _mock_web():
    """Activate web mocking for tests that need it."""
    with requests_mock.Mocker() as m:
        mock_requests_get(m)
        yield m
