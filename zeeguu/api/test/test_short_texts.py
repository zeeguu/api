"""Short texts a learner brings (a WhatsApp message...) are kept and read word by word."""

import uuid

import pytest

from fixtures import LoggedInClient, add_context_types, add_source_types
from fixtures import logged_in_client as client

import zeeguu.api.endpoints.short_texts as short_texts

GERMAN_MESSAGE = (
    "Hallo zusammen! Das Training morgen fällt leider aus, weil der Platz "
    "gesperrt ist. Wir sehen uns am Samstag beim Spiel."
)
FRENCH_MESSAGE = (
    "Bonjour à tous ! L'entraînement de demain est annulé parce que le terrain "
    "est fermé. On se retrouve samedi pour le match."
)


@pytest.fixture(autouse=True)
def _types(app):
    with app.app_context():
        add_source_types()
        add_context_types()


def _add(client, text, **extra):
    return client.response_from_post("/short_texts", data=dict(text=text, **extra))


def _read(client, text, **extra):
    return client.get(f"/short_texts/{_add(client, text, **extra).json['id']}")


def _words(paragraphs):
    return [token["text"] for par in paragraphs for sent in par for token in sent]


def test_text_in_learned_language_is_kept_and_tokenized_for_the_reader(client):
    result = _read(client, GERMAN_MESSAGE)

    assert result["language"] == "de"
    assert result["text"] == GERMAN_MESSAGE
    assert result["source_id"]
    # one paragraph (one line) of three sentences, as InteractiveText expects
    [line] = result["tokenized_paragraphs"]
    assert len(line) == 3
    assert "Training" in _words([line])


def test_each_line_is_a_paragraph_and_sentences_are_numbered_across_lines(client):
    paragraphs = _read(client, "Treffpunkt: 9:30. Am Platz.\n\nBitte Wasser mitbringen")["tokenized_paragraphs"]

    assert [_words([p]) for p in paragraphs] == [
        ["Treffpunkt", ":", "9:30", ".", "Am", "Platz", "."],
        ["Bitte", "Wasser", "mitbringen"],
    ]
    # bookmarks are found again by (sentence, token): no restart per line
    assert [[s[0]["sent_i"] for s in p] for p in paragraphs] == [[0, 1], [2]]
    assert {t["paragraph_i"] for s in paragraphs[1] for t in s} == {1}


def test_the_same_text_twice_is_one_text(client):
    first = _add(client, GERMAN_MESSAGE).json["id"]
    second = _add(client, "  " + GERMAN_MESSAGE + "\n").json["id"]

    assert first == second
    assert [each["id"] for each in client.get("/short_texts")] == [first]


def test_two_learners_share_the_stored_text_but_not_their_lists(client, app):
    mine = _add(client, GERMAN_MESSAGE).json["id"]

    other = LoggedInClient(app.test_client(), email="other@mir.lu", username="other")
    assert other.client.get(other.append_session(f"/short_texts/{mine}")).status_code == 404
    assert other.get("/short_texts") == []

    theirs = _add(other, GERMAN_MESSAGE).json["id"]
    assert theirs == mine


def test_list_is_most_recently_opened_first_with_a_preview(client):
    older = _add(client, GERMAN_MESSAGE).json["id"]
    newer = _add(client, "Bitte Wasser mitbringen").json["id"]
    assert [each["id"] for each in client.get("/short_texts")] == [newer, older]

    client.get(f"/short_texts/{older}")

    listed = client.get("/short_texts")
    assert [each["id"] for each in listed] == [older, newer]
    assert listed[0]["preview"].startswith("Hallo zusammen!")
    assert len(listed[0]["preview"]) <= 121
    assert listed[0]["language"] == "de"


def test_forgetting_a_text_takes_it_off_the_list(client):
    text_id = _add(client, GERMAN_MESSAGE).json["id"]

    assert client.client.delete(client.append_session(f"/short_texts/{text_id}")).status_code == 200

    assert client.get("/short_texts") == []
    assert client.client.get(client.append_session(f"/short_texts/{text_id}")).status_code == 404


def test_text_clearly_in_another_readable_language_is_read_in_that_language(client):
    assert _read(client, FRENCH_MESSAGE)["language"] == "fr"


def test_a_short_message_stays_in_the_learned_language(client):
    # Too short for langdetect to be trusted over what the learner learns
    assert _read(client, "Ok 👍")["language"] == "de"


def test_learned_language_wins_when_it_is_among_the_candidates(client, monkeypatch):
    from langdetect.language import Language as Guess

    # Close languages split the vote, e.g. Danish read as mostly Norwegian
    monkeypatch.setattr(
        short_texts, "detect_langs", lambda text: [Guess("fr", 0.8), Guess("de", 0.2)]
    )
    assert _read(client, GERMAN_MESSAGE)["language"] == "de"


def test_correcting_the_language_replaces_the_text_in_the_list(client):
    wrong = _add(client, GERMAN_MESSAGE).json["id"]

    right = _add(client, GERMAN_MESSAGE, language="nl", instead_of=wrong).json["id"]

    assert right != wrong
    assert client.get(f"/short_texts/{right}")["language"] == "nl"
    assert [each["id"] for each in client.get("/short_texts")] == [right]


def test_language_zeeguu_cannot_read_is_refused(client):
    assert _add(client, GERMAN_MESSAGE, language="fi").status_code == 406


def test_no_language_to_read_in_is_refused_not_a_crash(client, monkeypatch):
    # An account with no learned language, and langdetect unsure
    monkeypatch.setattr(short_texts, "guess_language", lambda text, learned: None)
    assert _add(client, GERMAN_MESSAGE).status_code == 406


def test_empty_text_is_refused(client):
    assert _add(client, "   ").status_code == 400


def test_overlong_text_is_refused(client):
    too_long = "Wort " * (short_texts.MAX_SHORT_TEXT_CHARS // 5 + 1)
    assert _add(client, too_long).status_code == 413


def test_whole_text_translation(client, monkeypatch):
    calls = []

    def fake_translate(text, from_lang, to_lang):
        calls.append((text, from_lang, to_lang))
        return "Hello everyone!"

    monkeypatch.setattr(short_texts, "translate_whole_text", fake_translate)
    text_id = _add(client, "Hallo zusammen!").json["id"]

    response = client.response_from_post(f"/short_texts/{text_id}/translate/en")

    assert response.status_code == 200
    assert response.json == {"translation": "Hello everyone!"}
    assert calls == [("Hallo zusammen!", "de", "en")]


def test_failed_whole_text_translation_is_reported(client, monkeypatch):
    monkeypatch.setattr(short_texts, "translate_whole_text", lambda *a: None)
    text_id = _add(client, "Hallo zusammen!").json["id"]

    assert client.response_from_post(f"/short_texts/{text_id}/translate/en").status_code == 502


def test_cannot_translate_someone_elses_text(client):
    assert client.response_from_post("/short_texts/123456/translate/en").status_code == 404


def test_tapped_word_becomes_a_bookmark_shown_again_on_reopening(client):
    """Through /translate_word, the way the reader sends a tap. (Tests run
    with DEV_SKIP_TRANSLATION, so no translator is called.)"""
    from zeeguu.core.model import Bookmark
    from zeeguu.core.model.context_type import ContextType

    text = _read(client, GERMAN_MESSAGE)

    result = client.post(
        "/translate_word/de/en",
        json={
            "word": "Training",
            "context": "Das Training morgen fällt leider aus",
            "source_id": text["source_id"],
            "w_sent_i": 0,
            "w_token_i": 1,
            "w_total_tokens": 1,
            "c_paragraph_i": 0,
            "c_sent_i": 1,
            "c_token_i": 0,
            "left_ellipsis": False,
            "right_ellipsis": False,
            "context_identifier": {"context_type": ContextType.SHORT_TEXT},
            "translation_source": "reading",
        },
    )

    bookmark = Bookmark.find(result["bookmark_id"])
    assert bookmark.context.context_type.type == ContextType.SHORT_TEXT
    assert bookmark.source_id == text["source_id"]

    reopened = client.get(f"/short_texts/{text['id']}")
    assert [b["id"] for b in reopened["past_bookmarks"]] == [bookmark.id]


def test_tokens_are_computed_once(client, monkeypatch):
    calls = []
    real = short_texts.tokenize_for_reader

    def counting(text, language):
        calls.append(text)
        return real(text, language)

    monkeypatch.setattr(short_texts, "tokenize_for_reader", counting)
    text_id = _add(client, GERMAN_MESSAGE).json["id"]

    first = client.get(f"/short_texts/{text_id}")
    second = client.get(f"/short_texts/{text_id}")

    assert len(calls) == 1
    assert first["tokenized_paragraphs"] == second["tokenized_paragraphs"]


def test_whole_text_translation_is_kept_per_language(client, monkeypatch):
    calls = []

    def fake_translate(text, from_lang, to_lang):
        calls.append(to_lang)
        return f"translated to {to_lang}"

    monkeypatch.setattr(short_texts, "translate_whole_text", fake_translate)
    text_id = _add(client, "Hallo zusammen!").json["id"]

    for to in ["en", "en", "da"]:
        client.response_from_post(f"/short_texts/{text_id}/translate/{to}")

    assert calls == ["en", "da"]
    assert client.post(f"/short_texts/{text_id}/translate/en") == {"translation": "translated to en"}


def test_translating_into_an_unknown_language_is_refused(client, monkeypatch):
    monkeypatch.setattr(short_texts, "translate_whole_text", lambda *a: pytest.fail("translator called"))
    text_id = _add(client, "Hallo zusammen!").json["id"]

    assert client.response_from_post(f"/short_texts/{text_id}/translate/undefined").status_code == 406


def _forget(client, text_id):
    return client.client.delete(client.append_session(f"/short_texts/{text_id}"))


def test_forgetting_the_last_copy_deletes_the_text_but_keeps_the_words(client, monkeypatch):
    from zeeguu.core.model import Bookmark, ShortText
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_text import SourceText

    monkeypatch.setattr(short_texts, "translate_whole_text", lambda *a: "Hello")
    # A text of its own: source and source_text outlive each test (conftest
    # _KEEP_TABLES), and a source left from another test would keep the
    # content alive, rightly
    text = _read(client, f"{GERMAN_MESSAGE} {uuid.uuid4().hex}")
    client.response_from_post(f"/short_texts/{text['id']}/translate/en")
    bookmark_id = client.post(
        "/translate_word/de/en",
        json={
            "word": "Training",
            "context": "Das Training morgen fällt leider aus",
            "source_id": text["source_id"],
            "w_sent_i": 0, "w_token_i": 1, "w_total_tokens": 1,
            "c_paragraph_i": 0, "c_sent_i": 1, "c_token_i": 0,
            "context_identifier": {"context_type": "ShortText"},
        },
    )["bookmark_id"]
    source_text_id = Source.find_by_id(text["source_id"]).source_text_id

    assert _forget(client, text["id"]).status_code == 200

    assert ShortText.find_by_id(text["id"]) is None
    assert Source.find_by_id(text["source_id"]) is None
    assert SourceText.query.filter_by(id=source_text_id).one_or_none() is None
    bookmark = Bookmark.find(bookmark_id)
    assert bookmark.source_id is None
    assert "Training" in bookmark.context.get_content()


def test_forgetting_keeps_the_text_for_other_learners(client, app):
    from zeeguu.core.model import ShortText

    text_id = _add(client, GERMAN_MESSAGE).json["id"]
    other = LoggedInClient(app.test_client(), email="other@mir.lu", username="other")
    _add(other, GERMAN_MESSAGE)

    _forget(client, text_id)

    assert ShortText.find_by_id(text_id) is not None
    assert other.get(f"/short_texts/{text_id}")["text"] == GERMAN_MESSAGE


def test_a_duplicate_source_from_a_race_does_not_break_adding(client, app):
    # Nothing keeps (text, type, language) unique in source; two learners
    # adding the same text at once can leave two rows
    from zeeguu.core.model.db import db
    from zeeguu.core.model.language import Language
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_text import SourceText
    from zeeguu.core.model.source_type import SourceType

    source_text = SourceText.find_or_create(db.session, GERMAN_MESSAGE)
    for _ in range(2):
        db.session.add(Source(source_text, SourceType.find_by_type(SourceType.SHORT_TEXT), Language.find("de")))
    db.session.commit()

    first = _add(client, GERMAN_MESSAGE)
    second = _add(client, GERMAN_MESSAGE)

    assert first.status_code == second.status_code == 200
    assert first.json["id"] == second.json["id"]
