from unittest import TestCase

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.word_list import WordList, WordListEntry
from zeeguu.core.test.model_test_mixin import ModelTestMixIn

ROWS = [
    {"section": "Substantiver", "phrase": "En konsekvens af", "translation": "A consequence of",
     "example": "En konsekvens af stress er søvnproblemer."},
    {"section": "Substantiver", "phrase": "Mangel på", "translation": "Lack of", "example": ""},
    {"section": "Adverbier", "phrase": "Derfor", "translation": "Therefore", "example": "Derfor gik jeg."},
]


class WordListTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.word_list = WordList(name="PD3", language=Language.find_or_create("da"))
        db.session.add(self.word_list)

    def test_import_keeps_order_and_blanks_become_null(self):
        assert self.word_list.import_entries(ROWS) == (3, 0, 0)
        db.session.commit()

        entries = WordList.find("PD3", Language.find("da")).entries
        assert [e.phrase for e in entries] == ["En konsekvens af", "Mangel på", "Derfor"]
        assert entries[1].example is None

    def test_reimport_updates_in_place_and_removes_dropped_entries(self):
        self.word_list.import_entries(ROWS)
        db.session.commit()
        kept_id = self.word_list.entries[0].id

        corrected = [dict(ROWS[0], translation="A result of"), ROWS[2]]
        assert self.word_list.import_entries(corrected) == (0, 2, 1)
        db.session.commit()

        assert [e.phrase for e in self.word_list.entries] == ["En konsekvens af", "Derfor"]
        assert self.word_list.entries[0].id == kept_id
        assert self.word_list.entries[0].translation == "A result of"
        assert WordListEntry.query.count() == 2

    def test_repeated_phrase_in_file_is_imported_once(self):
        assert self.word_list.import_entries(ROWS + [ROWS[0]]) == (3, 0, 0)
