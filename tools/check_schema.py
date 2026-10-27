#!/usr/bin/env python
"""
Fail if the database lacks a table or column that the models use.

The deploy script (ops running/api/restart.sh) runs this before switching
traffic, so code whose migration was never run does not go live: on 27 Oct
2026 the WordReport.outcome column was deployed without
26-10-25-c--word_report_outcome.sql and every exercise issue report failed.

Only missing tables and columns count. Extra ones in the database are fine:
migrations run before the deploy, and some columns stay unused until a later
migration drops them. Types are not compared.

Deliberately does not use create_app_for_scripts(): it calls db.create_all(),
which would build a missing table from the model before we could see it is
missing.

Usage:
    python -m tools.check_schema

Exit code 0 when the schema has everything the models need, 1 otherwise.
"""

import os
import re
import sys

MIGRATIONS_FOLDER = os.path.join(os.path.dirname(__file__), "migrations")


def missing_from_database(metadata, inspector):
    """
    Returns (missing_tables, missing_columns): table names, and
    (table, column) pairs, that the metadata has and the database doesn't.
    """
    # MySQL on Linux compares table names case-sensitively, but a model
    # declaring "User" for a table created as "user" is not what we hunt here
    db_tables = {name.lower(): name for name in inspector.get_table_names()}

    missing_tables = []
    missing_columns = []
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        db_name = db_tables.get(table.name.lower())
        if db_name is None:
            missing_tables.append(table.name)
            continue
        db_columns = {c["name"].lower() for c in inspector.get_columns(db_name)}
        for column in table.columns:
            if column.name.lower() not in db_columns:
                missing_columns.append((table.name, column.name))

    return missing_tables, missing_columns


def migrations_matching(*patterns):
    """The migration files that match all the given regexes; a hint, not a proof."""
    found = []
    for file_name in sorted(os.listdir(MIGRATIONS_FOLDER)):
        if not file_name.endswith(".sql"):
            continue
        with open(os.path.join(MIGRATIONS_FOLDER, file_name), errors="replace") as f:
            content = f.read()
        if all(re.search(p, content, re.IGNORECASE) for p in patterns):
            found.append(file_name)
    return found


def creating_table(table):
    # CREATE TABLE [IF NOT EXISTS] [`]table[`]
    return rf"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?`?{re.escape(table)}`?[\s(]"


def adding_column(table, column):
    return [rf"ALTER\s+TABLE\s+`?{re.escape(table)}`?\s", rf"ADD\s+(COLUMN\s+)?`?{re.escape(column)}\b"]


def main():
    from flask import Flask
    from sqlalchemy import create_engine, inspect

    from zeeguu.config.loader import load_configuration_or_abort

    # Importing the packages registers every model with db.metadata
    import zeeguu.core.model  # noqa: F401
    import zeeguu.core.word_scheduling  # noqa: F401
    from zeeguu.core.model.db import db

    app = Flask("Zeeguu-SchemaCheck")
    load_configuration_or_abort(app, "ZEEGUU_CONFIG", ["SQLALCHEMY_DATABASE_URI"])

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    try:
        missing_tables, missing_columns = missing_from_database(
            db.metadata, inspect(engine)
        )
    finally:
        engine.dispose()

    if not missing_tables and not missing_columns:
        print(f"Schema OK: the database has all {len(db.metadata.tables)} model tables and their columns.")
        return 0

    print("The database lacks what the models use. Run the migration first:")
    for table in missing_tables:
        hint = migrations_matching(creating_table(table))
        print(f"  table {table}" + (f"  (see {', '.join(hint)})" if hint else ""))
    for table, column in missing_columns:
        hint = migrations_matching(*adding_column(table, column))
        print(f"  column {table}.{column}" + (f"  (see {', '.join(hint)})" if hint else ""))
    return 1


if __name__ == "__main__":
    sys.exit(main())
