"""tools/check_schema.py: the deploy fails on a table or column the models use and the
database lacks, and not on extra ones."""
from unittest import TestCase

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

from tools.check_schema import (
    adding_column,
    creating_table,
    migrations_matching,
    missing_from_database,
)


def _models():
    metadata = MetaData()
    Table("word_report", metadata, Column("id", Integer, primary_key=True), Column("outcome", String(20)))
    Table("feed", metadata, Column("id", Integer, primary_key=True))
    return metadata


class CheckSchemaTest(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE word_report (id INTEGER PRIMARY KEY, reason TEXT)")

    def tearDown(self):
        self.engine.dispose()

    def test_reports_missing_table_and_column(self):
        tables, columns = missing_from_database(_models(), inspect(self.engine))

        assert tables == ["feed"]
        assert columns == [("word_report", "outcome")]

    def test_extra_columns_and_tables_in_the_database_are_fine(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE word_report ADD COLUMN outcome TEXT")
            connection.exec_driver_sql("CREATE TABLE feed (id INTEGER PRIMARY KEY, unused TEXT)")
            connection.exec_driver_sql("CREATE TABLE legacy (id INTEGER PRIMARY KEY)")

        assert missing_from_database(_models(), inspect(self.engine)) == ([], [])

    def test_hints_at_the_migration_that_adds_the_column(self):
        assert migrations_matching(*adding_column("word_report", "outcome")) == [
            "26-10-25-c--word_report_outcome.sql"
        ]
        assert "26-10-25-b--word_report.sql" in migrations_matching(creating_table("word_report"))


class CheckSchemaAgainstTheModelsTest(TestCase):
    def test_a_database_built_from_the_models_passes(self):
        import zeeguu.core.model  # noqa: F401
        import zeeguu.core.word_scheduling  # noqa: F401
        from zeeguu.core.model.db import db

        engine = create_engine("sqlite://")
        db.metadata.create_all(engine)

        assert "word_report" in db.metadata.tables
        assert "basic_sr_schedule" in db.metadata.tables
        assert missing_from_database(db.metadata, inspect(engine)) == ([], [])
        engine.dispose()
