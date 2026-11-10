"""
Generated examples are written at the learner's level. The web never sends a
cefr_level, so these endpoints used to ask for every example at B1, also for
A2 school classes (feedback from user 6885, 9 Nov 2026).
"""

from zeeguu.api.endpoints import generated_examples
from zeeguu.api.endpoints.generated_examples import _levels_up_to
from zeeguu.api.test.fixtures import logged_in_client
from zeeguu.core.model import Language, User, UserLanguage
from zeeguu.core.model.db import db


class _RecordingLLM:
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


def _requested_level(client, monkeypatch, url):
    llm = _RecordingLLM()
    monkeypatch.setattr(generated_examples, "get_llm_service", lambda **kwargs: llm)
    client.get(url)
    return llm.levels


def test_examples_are_written_at_the_learners_level(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, 2)  # A2

    assert _requested_level(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en") == ["A2"]


def test_an_explicit_level_still_wins(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, 2)

    levels = _requested_level(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en?cefr_level=C1")
    assert levels == ["C1"]


def test_without_a_level_examples_fall_back_to_a2(logged_in_client, monkeypatch):
    _set_german_level(logged_in_client.email, None)

    assert _requested_level(logged_in_client, monkeypatch, "/generate_examples/Haus/de/en") == ["A2"]


def test_levels_up_to():
    assert _levels_up_to("A2") == ["A1", "A2"]
    assert _levels_up_to("A1") == ["A1"]
    assert _levels_up_to("C2") == ["A1", "A2", "B1", "B2", "C1", "C2"]
