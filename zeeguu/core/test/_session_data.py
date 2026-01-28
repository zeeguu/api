"""
One-time expensive test data created at session scope.

Loads pre-computed article + NLP data from a JSON fixture file,
avoiding the ~25s Stanza NLP pipeline on every test run.

To regenerate the fixture after schema changes, run:
    source ~/.venvs/z_env/bin/activate && python tools/regenerate_test_fixture.py
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
