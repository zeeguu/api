"""When the translators disagree on a lookup, an LLM settles it and the
bookmark moves to its answer, unless the learner got there first."""
from unittest.mock import patch

from fixtures import (
    logged_in_client as client,
    add_context_types,
    add_source_types,
    add_one_bookmark,
)
from zeeguu.core.llm_services.translation_disagreement_resolver import Resolution
from zeeguu.core.model import Bookmark, TranslationService

RESOLVER = "zeeguu.core.llm_services.translation_disagreement_resolver.resolve_translation_disagreement"


def _resolve(client, bookmark_id, shown="behind", candidates=("behind", "after")):
    return client.post(
        "/resolve_translation_disagreement/de/en",
        json={
            "word": "hinter",
            "context": "stellt sich hinter Präsident",
            "candidates": list(candidates),
            "shown": shown,
            "bookmark_id": bookmark_id,
        },
    )


def _translation(bookmark_id):
    return Bookmark.find(bookmark_id).user_word.meaning.translation.content


def test_a_different_answer_moves_the_bookmark(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    with patch(RESOLVER, return_value=Resolution("backs", "Here: to support someone.")):
        result = _resolve(client, bookmark_id)

    assert result == {"translation": "backs", "reason": "Here: to support someone.", "changed": True}
    assert _translation(bookmark_id) == "backs"
    assert Bookmark.find(bookmark_id).translation_service.name == TranslationService.DISAGREEMENT_RESOLVER


def test_the_same_answer_changes_nothing(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    with patch(RESOLVER, return_value=Resolution("Behind", "")):
        result = _resolve(client, bookmark_id)

    assert result["changed"] is False
    assert _translation(bookmark_id) == "behind"
    assert Bookmark.find(bookmark_id).translation_service.name == TranslationService.MANUAL


def test_a_translation_the_learner_changed_meanwhile_is_kept(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    client.post(f"/update_bookmark_translation/{bookmark_id}", json={"translation": "after"})
    with patch(RESOLVER, return_value=Resolution("backs", "")):
        result = _resolve(client, bookmark_id, shown="behind")

    assert result["changed"] is False
    assert _translation(bookmark_id) == "after"


def test_no_bookmark_still_gets_an_answer(client):
    with patch(RESOLVER, return_value=Resolution("backs", "")):
        result = _resolve(client, None)
    assert result["translation"] == "backs"


def test_a_failed_llm_call_is_a_404(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    with patch(RESOLVER, return_value=None):
        response = client.client.post(
            client.append_session("/resolve_translation_disagreement/de/en"),
            json={"word": "hinter", "context": "x", "candidates": ["behind"], "shown": "behind",
                  "bookmark_id": bookmark_id},
        )
    assert response.status_code == 404
    assert _translation(bookmark_id) == "behind"
