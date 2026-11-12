"""A message shared in from another app (WhatsApp...) is readable word by word."""

from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types

import zeeguu.api.endpoints.shared_text as shared_text

GERMAN_MESSAGE = (
    "Hallo zusammen! Das Training morgen fällt leider aus, weil der Platz "
    "gesperrt ist. Wir sehen uns am Samstag beim Spiel."
)
FRENCH_MESSAGE = (
    "Bonjour à tous ! L'entraînement de demain est annulé parce que le terrain "
    "est fermé. On se retrouve samedi pour le match."
)


def _prepare(client, text, **extra):
    return client.response_from_post("/shared_text/prepare", data=dict(text=text, **extra))


def _words(tokenized):
    return [token["text"] for par in tokenized for sent in par for token in sent]


def test_message_in_learned_language_is_tokenized_for_the_reader(client):
    response = _prepare(client, GERMAN_MESSAGE)

    assert response.status_code == 200
    result = response.json
    assert result["language"] == "de"
    # one line; in it paragraphs -> sentences -> tokens, as InteractiveText expects
    [line] = result["tokenized_lines"]
    assert len(line) == 1 and len(line[0]) == 3
    assert "Training" in _words(line)


def test_each_line_of_a_message_stays_a_line(client):
    lines = _prepare(client, "Treffpunkt:\n9:30 am Platz\n\nBitte Wasser mitbringen").json["tokenized_lines"]

    assert [_words(line) for line in lines] == [
        ["Treffpunkt", ":"],
        ["9:30", "am", "Platz"],
        ["Bitte", "Wasser", "mitbringen"],
    ]


def test_message_clearly_in_another_readable_language_is_read_in_that_language(client):
    assert _prepare(client, FRENCH_MESSAGE).json["language"] == "fr"


def test_a_short_message_stays_in_the_learned_language(client):
    # Too short for langdetect to be trusted over what the learner learns
    assert _prepare(client, "Ok 👍").json["language"] == "de"


def test_learned_language_wins_when_it_is_among_the_candidates(client, monkeypatch):
    from langdetect.language import Language as Guess

    # Close languages split the vote, e.g. Danish read as mostly Norwegian
    monkeypatch.setattr(
        shared_text, "detect_langs", lambda text: [Guess("fr", 0.8), Guess("de", 0.2)]
    )
    assert _prepare(client, GERMAN_MESSAGE).json["language"] == "de"


def test_learner_can_correct_the_language(client):
    assert _prepare(client, GERMAN_MESSAGE, language="nl").json["language"] == "nl"


def test_language_zeeguu_cannot_read_is_refused(client):
    assert _prepare(client, GERMAN_MESSAGE, language="fi").status_code == 406


def test_empty_message_is_refused(client):
    assert _prepare(client, "   ").status_code == 400


def test_overlong_message_is_refused(client):
    too_long = "Wort " * (shared_text.MAX_SHARED_TEXT_CHARS // 5 + 1)
    assert _prepare(client, too_long).status_code == 413


def test_whole_message_translation(client, monkeypatch):
    calls = []

    def fake_translate(text, from_lang, to_lang):
        calls.append((text, from_lang, to_lang))
        return "Hello everyone!"

    monkeypatch.setattr(shared_text, "translate_whole_text", fake_translate)

    response = client.response_from_post(
        "/shared_text/translate/de/en", data=dict(text="Hallo zusammen!")
    )

    assert response.status_code == 200
    assert response.json == {"translation": "Hello everyone!"}
    assert calls == [("Hallo zusammen!", "de", "en")]


def test_failed_whole_message_translation_is_reported(client, monkeypatch):
    monkeypatch.setattr(shared_text, "translate_whole_text", lambda *a: None)
    response = client.response_from_post(
        "/shared_text/translate/de/en", data=dict(text="Hallo zusammen!")
    )
    assert response.status_code == 502


def test_no_language_to_read_in_is_refused_not_a_crash(client, monkeypatch):
    # An account with no learned language, and langdetect unsure
    monkeypatch.setattr(shared_text, "guess_language", lambda text, learned: None)
    assert _prepare(client, GERMAN_MESSAGE).status_code == 406


def test_tapped_word_in_a_shared_text_becomes_a_bookmark(client):
    """Through /translate_word, the way the reader sends a tap. (Tests run
    with DEV_SKIP_TRANSLATION, so no translator is called.)"""
    from zeeguu.core.model import Bookmark
    from zeeguu.core.model.context_type import ContextType

    add_context_types()
    add_source_types()

    # No article, no source: the text only exists on the learner's phone
    result = client.post(
        "/translate_word/de/en",
        json={
            "word": "Training",
            "context": "Das Training morgen fällt leider aus",
            "source_id": None,
            "w_sent_i": 0,
            "w_token_i": 1,
            "w_total_tokens": 1,
            "c_paragraph_i": 0,
            "c_sent_i": 0,
            "c_token_i": 0,
            "left_ellipsis": False,
            "right_ellipsis": False,
            "context_identifier": {"context_type": ContextType.SHARED_TEXT},
            "translation_source": "reading",
        },
    )

    bookmark = Bookmark.find(result["bookmark_id"])
    assert bookmark.context.context_type.type == ContextType.SHARED_TEXT
    assert bookmark.source_id is None
