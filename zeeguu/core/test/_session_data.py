"""
One-time expensive test data created at session scope.

Loads pre-computed article + NLP data from a JSON fixture file,
avoiding the ~25s Stanza NLP pipeline on every test run.

To regenerate the fixture after schema changes, run:
    source ~/.venvs/z_env/bin/activate && python zeeguu/core/test/_session_data.py
"""

import json
import os

from sqlalchemy import text

from zeeguu.core.model.db import db

_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "test_data", "session_fixture.json"
)


def load_session_fixture():
    """
    Load pre-computed article fixture data into the test DB.
    Skips Stanza/torch entirely — loads in <0.1s instead of ~25s.
    """
    with open(_FIXTURE_PATH) as f:
        dump = json.load(f)

    # Insert in order (respects FK dependencies)
    for table_name, table_data in dump.items():
        columns = table_data["columns"]
        rows = table_data["rows"]
        if not rows:
            continue

        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'

        for row in rows:
            params = {}
            for col, val in zip(columns, row):
                params[col] = val
            db.session.execute(text(sql), params)

    db.session.commit()


if __name__ == "__main__":
    # Regenerate the fixture file
    import requests_mock as rm
    from zeeguu.api.app import create_app
    from zeeguu.core.test.mocking_the_web import (
        mock_requests_get,
        URL_SPIEGEL_VENEZUELA,
    )

    KEEP_TABLES = [
        "language", "context_type", "source_type", "domain_name",
        "url", "url_keyword", "source", "source_text",
        "article", "article_fragment", "article_cefr_assessment",
        "article_tokenization_cache", "article_url_keyword_map", "new_text",
    ]

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

                with open(_FIXTURE_PATH, "w") as f:
                    json.dump(dump, f)
                print(f"Wrote {_FIXTURE_PATH}")
