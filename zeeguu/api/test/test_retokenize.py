"""After a tokenization change, every cached token stream in one language is
redone; other languages are left alone."""

import pytest

from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText

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

    row_id = _level_adapted_row(client).id
    done, kept = retokenize.retokenize_level_adapted(db.session, Language.find("de"), progress=lambda _: None)

    assert (done, kept) == (1, 0)
    row = db.session.get(LevelAdaptedArticleText, row_id)
    assert row.tokenized_summary != ["old"]
    assert "Training" in str(row.tokenized_summary)


def test_a_level_adapted_text_that_fails_keeps_its_old_tokens(client, monkeypatch):
    import zeeguu.core.mwe
    from zeeguu.core.model import db
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    row_id = _level_adapted_row(client).id

    def broken(*args, **kwargs):
        raise RuntimeError("stanza down")

    monkeypatch.setattr(zeeguu.core.mwe, "tokenize_for_reading", broken)
    done, kept = retokenize.retokenize_level_adapted(db.session, Language.find("de"), progress=lambda _: None)

    assert (done, kept) == (0, 1)
    assert db.session.get(LevelAdaptedArticleText, row_id).tokenized_summary == ["old"]


def test_exercise_sentences_are_retokenized_in_place(client):
    from zeeguu.core.model import db
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    context = db.session.get(Bookmark, add_one_bookmark(client)).context
    context.cached_tokenized = ["old"]
    db.session.commit()
    context_id = context.id

    done, kept = retokenize.retokenize_bookmark_contexts(db.session, Language.find("de"), progress=lambda _: None)

    assert (done, kept) == (1, 0)
    assert db.session.get(BookmarkContext, context_id).cached_tokenized != ["old"]


def test_a_whole_run_leaves_other_languages_alone(client):
    # Both steps in sequence with one Language, as the tool runs them; and a
    # run for French touches none of the German rows.
    from zeeguu.core.model import db
    from zeeguu.core.model.bookmark import Bookmark
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    bookmark_id = add_one_bookmark(client)
    row_id = _level_adapted_row(client).id
    # Fetched after the requests above: each ends the session it ran in
    context = db.session.get(Bookmark, bookmark_id).context
    row = db.session.get(LevelAdaptedArticleText, row_id)
    context.cached_tokenized = ["old"]
    row.title = GERMAN
    db.session.commit()
    context_id = context.id

    quiet = lambda _: None
    fr = Language.find_or_create("fr")
    retokenize.clear_rebuildable(db.session, fr)
    assert retokenize.retokenize_bookmark_contexts(db.session, fr, quiet) == (0, 0)
    assert retokenize.retokenize_level_adapted(db.session, fr, quiet) == (0, 0)

    de = Language.find("de")
    assert retokenize.retokenize_bookmark_contexts(db.session, de, quiet) == (1, 0)
    assert retokenize.retokenize_level_adapted(db.session, de, quiet) == (1, 0)

    assert db.session.get(BookmarkContext, context_id).cached_tokenized != ["old"]
    row = db.session.get(LevelAdaptedArticleText, row_id)
    assert row.tokenized_summary != ["old"]
    assert "Training" in str(row.tokenized_title)


def test_the_article_cache_of_the_language_is_dropped(client):
    from zeeguu.core.model import db
    from zeeguu.core.model.article import Article
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    article = db.session.get(Article, create_and_get_article(client)["id"])
    article.get_tokenized_content()  # caches it
    de = Language.find("de")
    assert retokenize.count_cached(db.session, de)["articles"] == 1

    retokenize.clear_rebuildable(db.session, de)
    assert retokenize.count_cached(db.session, de)["articles"] == 0


def test_a_run_stops_when_stanza_keeps_failing(client, monkeypatch):
    import zeeguu.core.mwe
    from zeeguu.core.model import db
    from zeeguu.core.model.language import Language
    from zeeguu.core.tokenization import retokenize

    _level_adapted_row(client)
    monkeypatch.setattr(retokenize, "MAX_FAILURES_IN_A_ROW", 1)
    monkeypatch.setattr(zeeguu.core.mwe, "tokenize_for_reading", lambda *a, **k: 1 / 0)

    with pytest.raises(retokenize.StanzaGaveUp):
        retokenize.retokenize_level_adapted(db.session, Language.find("de"), progress=lambda _: None)
