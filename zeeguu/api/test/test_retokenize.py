"""After a tokenization change, every cached token stream in one language is
redone; other languages are left alone."""

import pytest

from fixtures import add_context_types, add_one_bookmark, add_source_types, create_and_get_article
from fixtures import logged_in_client as client

GERMAN = "Das Training morgen fällt leider aus."
FRENCH = "L'entraînement de demain est annulé."


@pytest.fixture(autouse=True)
def _types(app):
    with app.app_context():
        add_source_types()
        add_context_types()


def _read_short_text(client, text, language):
    added = client.response_from_post("/short_texts", data=dict(text=text, language=language))
    client.get(f"/short_texts/{added.json['id']}")
    return added.json["id"]


def test_pasted_texts_in_the_language_are_cleared_and_others_kept(client):
    from zeeguu.core.model import db
    from zeeguu.core.model.language import Language
    from zeeguu.core.model.short_text import ShortText
    from zeeguu.core.tokenization import retokenize

    german = _read_short_text(client, GERMAN, "de")
    french = _read_short_text(client, FRENCH, "fr")

    de = Language.find("de")
    assert retokenize.count_cached(db.session, de)["pasted texts"] == 1
    retokenize.clear_rebuildable(db.session, de)

    db.session.expire_all()
    assert db.session.get(ShortText, german).tokenized_paragraphs is None
    assert db.session.get(ShortText, french).tokenized_paragraphs is not None
    # and it comes back on the next read
    assert client.get(f"/short_texts/{german}")["tokenized_paragraphs"]


def _level_adapted_row(client):
    from zeeguu.core.model import db
    from zeeguu.core.model.article import Article
    from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText

    article = db.session.get(Article, create_and_get_article(client)["id"])
    return LevelAdaptedArticleText.find_or_create(
        db.session, article, "A2", summary=GERMAN, tokenized_summary=["old"]
    )


def test_level_adapted_summaries_are_retokenized_in_place(client):
    from zeeguu.core.model import db
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    row = _level_adapted_row(client)
    done, kept = retokenize.retokenize_level_adapted(db.session, Language.find("de"), progress=lambda _: None)

    assert (done, kept) == (1, 0)
    assert row.tokenized_summary != ["old"]
    assert "Training" in str(row.tokenized_summary)


def test_a_level_adapted_text_that_fails_keeps_its_old_tokens(client, monkeypatch):
    import zeeguu.core.mwe
    from zeeguu.core.model import db
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    row = _level_adapted_row(client)

    def broken(*args, **kwargs):
        raise RuntimeError("stanza down")

    monkeypatch.setattr(zeeguu.core.mwe, "tokenize_for_reading", broken)
    done, kept = retokenize.retokenize_level_adapted(db.session, Language.find("de"), progress=lambda _: None)

    assert (done, kept) == (0, 1)
    assert row.tokenized_summary == ["old"]


def test_exercise_sentences_are_retokenized_in_place(client):
    from zeeguu.core.model import db
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    context = db.session.get(Bookmark, add_one_bookmark(client)).context
    context.cached_tokenized = ["old"]
    db.session.commit()

    done, kept = retokenize.retokenize_bookmark_contexts(db.session, Language.find("de"), progress=lambda _: None)

    assert (done, kept) == (1, 0)
    assert context.cached_tokenized != ["old"]
