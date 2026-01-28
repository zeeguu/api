#!/usr/bin/env python
"""
Regenerate the test fixture file for session-scoped test data.

Run this after schema changes:
    source ~/.venvs/z_env/bin/activate && python tools/regenerate_test_fixture.py
"""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests_mock as rm
from zeeguu.api.app import create_app
from zeeguu.core.model.db import db
from zeeguu.core.test.mocking_the_web import (
    mock_requests_get,
    URL_SPIEGEL_VENEZUELA,
)
from sqlalchemy import text

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "zeeguu/core/test/test_data/session_fixture.json"
)

KEEP_TABLES = [
    "language", "context_type", "source_type", "domain_name",
    "url", "url_keyword", "source", "source_text",
    "article", "article_fragment", "article_cefr_assessment",
    "article_tokenization_cache", "article_url_keyword_map", "new_text",
]


def main():
    app = create_app(testing=True)
    with rm.Mocker() as m:
        mock_requests_get(m)
        with app.test_client() as client:
            with app.app_context():
                db.create_all()

                from zeeguu.core.model.context_type import ContextType as CT
                for t in CT.ALL_TYPES:
                    CT.find_or_create(db.session, t, commit=False)
                from zeeguu.core.model.source_type import SourceType as ST
                for t in ST.ALL_TYPES:
                    ST.find_or_create(db.session, t, commit=False)
                db.session.commit()

                resp = client.post(
                    "/add_user/dump@test.com",
                    data=dict(password="test", username="dump", learned_language="de"),
                )
                session_token = resp.data.decode("utf-8")
                client.post(
                    f"/find_or_create_article?session={session_token}",
                    data=dict(url=URL_SPIEGEL_VENEZUELA),
                )

                dump = {}
                for tname in KEEP_TABLES:
                    rows = db.session.execute(text(f'SELECT * FROM "{tname}"')).fetchall()
                    keys = list(db.session.execute(text(f'SELECT * FROM "{tname}"')).keys())
                    dump[tname] = {
                        "columns": keys,
                        "rows": [
                            [str(v) if v is not None else None for v in row]
                            for row in rows
                        ],
                    }
                    print(f"{tname}: {len(rows)} rows")

                with open(FIXTURE_PATH, "w") as f:
                    json.dump(dump, f)
                print(f"Wrote {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
