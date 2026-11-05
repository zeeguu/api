"""When the translators disagree on a lookup, an LLM settles it and the
bookmark moves to its answer, unless the learner got there first."""
from unittest.mock import patch

from sqlalchemy import text

from fixtures import (
    logged_in_client as client,
    add_context_types,
    add_source_types,
    add_one_bookmark,
)
from zeeguu.core.llm_services.translation_disagreement_resolver import Resolution
from zeeguu.core.model import Bookmark, Meaning, TranslationCorrection, TranslationService, db

RESOLVER = "zeeguu.core.llm_services.translation_disagreement_resolver.resolve_translation_disagreement"


def _resolve(client, bookmark_id, shown="behind", candidates=("behind", "after")):
    _make_dev(client)
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


def _make_dev(client):
    # The resolver is behind the dev-only resolve_disagreements feature.
    from zeeguu.core.model import User

    User.find(client.email).is_dev = True
    db.session.commit()


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
    # The LLM's answer is not the learner's correction: it must not be shared
    # with the next readers under the learner's name and trust.
    assert TranslationCorrection.query.count() == 0


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


def _from_another_request(sql, **params):
    # Committed past the session, which keeps its copies of the rows, as it
    # does when another request writes during the LLM call.
    db.session.execute(text(sql), params)
    db.session.connection().connection.commit()


def test_a_bookmark_deleted_meanwhile_is_left_alone(client):
    # Fusing a word into a phrase deletes its bookmark, often during the wait.
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)

    def delete_while_waiting(*_):
        _from_another_request("DELETE FROM bookmark WHERE id = :id", id=bookmark_id)
        return Resolution("backs", "")

    with patch(RESOLVER, side_effect=delete_while_waiting):
        result = _resolve(client, bookmark_id)

    assert result["changed"] is False


def test_a_translation_the_learner_changes_during_the_wait_is_kept(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    user_word = Bookmark.find(bookmark_id).user_word
    user_word_id = user_word.id
    picked = Meaning.find_or_create(db.session, "hinter", "de", "after", "en")
    db.session.commit()
    picked_id = picked.id

    def pick_while_waiting(*_):
        _from_another_request(
            "UPDATE user_word SET meaning_id = :meaning WHERE id = :id",
            meaning=picked_id,
            id=user_word_id,
        )
        return Resolution("backs", "")

    with patch(RESOLVER, side_effect=pick_while_waiting):
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
    _make_dev(client)
    with patch(RESOLVER, return_value=None):
        response = client.client.post(
            client.append_session("/resolve_translation_disagreement/de/en"),
            json={"word": "hinter", "context": "x", "candidates": ["behind"], "shown": "behind",
                  "bookmark_id": bookmark_id},
        )
    assert response.status_code == 404
    assert _translation(bookmark_id) == "behind"


def test_accounts_without_the_feature_are_refused(client):
    with patch(RESOLVER) as resolver:
        response = client.client.post(
            client.append_session("/resolve_translation_disagreement/de/en"),
            json={"word": "hinter", "context": "x", "candidates": ["behind"], "shown": "behind"},
        )
    assert response.status_code == 403
    resolver.assert_not_called()
