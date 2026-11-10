"""
Generated examples are written at the learner's level. The web never sends a
cefr_level, so these endpoints used to ask for every example at B1, also for
A2 school classes (feedback from user 6885, 9 Nov 2026).
"""

from zeeguu.api.endpoints import generated_examples
from zeeguu.core.exercises.example_contexts import usable_examples_query
from zeeguu.api.test.fixtures import logged_in_client
from zeeguu.core.model import Language, Meaning, User, UserLanguage
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.model.db import db


class FakeExampleWriter:
    """Stands in for the LLM: notes the level it is asked to write examples
    at, and writes none."""

    def __init__(self):
        self.levels = []

    def generate_examples(self, cefr_level, **kwargs):
        self.levels.append(cefr_level)
        return []


def _set_german_level(email, level):
    user = User.find(email)
    german = UserLanguage.find_or_create(db.session, user, Language.find("de"))
    german.cefr_level = level
    db.session.commit()


def levels_the_llm_was_asked_for(client, monkeypatch, url):
    """GETs `url` with FakeExampleWriter as the LLM and returns the levels
    the endpoint asked it to write at: [] when it used stored examples."""
    llm = FakeExampleWriter()
    monkeypatch.setattr(generated_examples, "get_llm_service", lambda **kwargs: llm)
    client.get(url)
    return llm.levels


def test_examples_are_written_at_the_learners_level(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, 2)  # A2

    assert levels_the_llm_was_asked_for(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en") == ["A2"]


def test_an_explicit_level_still_wins(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, 2)

    levels = levels_the_llm_was_asked_for(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en?cefr_level=C1")
    assert levels == ["C1"]


def test_without_a_level_examples_fall_back_to_a2(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, None)

    assert levels_the_llm_was_asked_for(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en") == ["A2"]


def _meaning_with_examples(*levels):
    meaning = Meaning.find_or_create(db.session, "Haus", "de", "house", "en")
    for i, level in enumerate(levels):
        db.session.add(ExampleSentence(f"Das Haus {i} {level}.", Language.find("de"), meaning, cefr_level=level))
    db.session.commit()
    return meaning


def _levels(examples):
    return [example.cefr_level for example in examples]


def test_one_example_at_the_level_does_not_hide_the_easier_ones(logged_in_client):
    meaning = _meaning_with_examples("A1", "A1", "A2", "A1", "B1")

    assert _levels(usable_examples_query(meaning.id, "A2").all()) == ["A2", "A1", "A1", "A1"]


def test_never_an_example_above_the_level(logged_in_client):
    meaning = _meaning_with_examples("B2", "C1")

    assert usable_examples_query(meaning.id, "A2").all() == []


def test_the_popup_reuses_easier_stored_examples(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, 2)  # A2
    _meaning_with_examples("A1", "B2")

    assert levels_the_llm_was_asked_for(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en?translation=house") == []


def test_a_level_we_dont_know_is_the_fallback_not_everything(logged_in_client):
    meaning = _meaning_with_examples("A1", "A2", "B1", "C2")

    assert _levels(usable_examples_query(meaning.id, "b1").all()) == ["A2", "A1"]
    assert _levels(usable_examples_query(meaning.id, "nonsense").all()) == ["A2", "A1"]


def test_a0_reads_the_a1_examples(logged_in_client):
    meaning = _meaning_with_examples("A1", "A2")

    assert _levels(usable_examples_query(meaning.id, "A0").all()) == ["A1"]
