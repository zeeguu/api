"""/preview_learning_card no longer writes the learner's level as the word's."""
from zeeguu.api.endpoints import generated_examples
from zeeguu.api.test.fixtures import logged_in_client
from zeeguu.core.model import Meaning
from zeeguu.core.model.db import db

CARD = {
    "word": "warum",
    "translation": "why",
    "example": "Warum bist du hier?",
    "explanation": "Question word for reasons.",
    "level_note": "appropriate for B1 - very common question word",
}

BODY = {"word": "warum", "translation": "why", "from_lang": "de", "to_lang": "en", "examples": []}


def test_the_level_note_does_not_become_the_words_level(logged_in_client, monkeypatch):
    monkeypatch.setattr(generated_examples, "prepare_learning_card", lambda **kwargs: dict(CARD))

    card = logged_in_client.post("/preview_learning_card", json=BODY)

    assert card["word_cefr_level"] is None
    assert Meaning.find_or_create(db.session, "warum", "de", "why", "en").word_cefr_level is None


def test_the_validators_level_is_shown(logged_in_client, monkeypatch):
    meaning = Meaning.find_or_create(db.session, "warum", "de", "why", "en")
    meaning.word_cefr_level = "A1"
    db.session.commit()
    monkeypatch.setattr(generated_examples, "prepare_learning_card", lambda **kwargs: dict(CARD))

    assert logged_in_client.post("/preview_learning_card", json=BODY)["word_cefr_level"] == "A1"
