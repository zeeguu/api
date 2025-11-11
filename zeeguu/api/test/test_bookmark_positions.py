"""
Tests for bookmark position tracking (token_i, sentence_i, total_tokens).

These tests ensure that:
1. Single-word bookmarks have correct positions
2. Multi-word bookmarks have correct positions
3. Bookmark updates recalculate positions correctly
4. Position data is never NULL for new bookmarks
"""

from fixtures import (
    logged_in_client as client,
    add_context_types,
    add_source_types,
)
from zeeguu.core.model import Bookmark
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType


def _create_bookmark_with_positions(client, word, context, sentence_i=0, token_i=0, total_tokens=1):
    """Helper to create a bookmark with position data."""
    add_context_types()
    add_source_types()

    # Create article
    from fixtures import create_and_get_article
    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_FRAGMENT, None, article["id"])

    # Create bookmark via translation endpoint
    response = client.post(
        "/get_one_translation/de/en",
        json={
            "word": word,
            "context": context,
            "source_id": article["source_id"],
            "w_sent_i": sentence_i,
            "w_token_i": token_i,
            "w_total_tokens": total_tokens,
            "c_sent_i": 0,
            "c_token_i": 0,
            "context_identifier": context_i.as_dictionary(),
        },
    )

    return response["bookmark_id"]


def test_single_word_bookmark_has_positions(client):
    """Test that single-word bookmarks are created with correct position data."""
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt laut",
        sentence_i=0,
        token_i=1,  # "Hund" is at position 1 (after "Der")
        total_tokens=1
    )

    # Verify position data is stored
    bookmark = Bookmark.find(bookmark_id)
    assert bookmark.sentence_i == 0, "sentence_i should be 0"
    assert bookmark.token_i == 1, "token_i should be 1"
    assert bookmark.total_tokens == 1, "total_tokens should be 1"
    assert bookmark.sentence_i is not None, "sentence_i should not be NULL"
    assert bookmark.token_i is not None, "token_i should not be NULL"


def test_multiword_bookmark_has_positions(client):
    """Test that multi-word bookmarks are created with correct position data."""
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="nicht mehr",
        context="Das ist nicht mehr möglich",
        sentence_i=0,
        token_i=2,  # "nicht" starts at position 2
        total_tokens=2  # "nicht mehr" is 2 tokens
    )

    # Verify position data is stored
    bookmark = Bookmark.find(bookmark_id)
    assert bookmark.sentence_i == 0, "sentence_i should be 0"
    assert bookmark.token_i == 2, "token_i should be at first token of phrase"
    assert bookmark.total_tokens == 2, "total_tokens should be 2 for multi-word"
    assert bookmark.sentence_i is not None, "sentence_i should not be NULL"
    assert bookmark.token_i is not None, "token_i should not be NULL"
    assert bookmark.total_tokens is not None, "total_tokens should not be NULL"


def test_bookmark_update_recalculates_positions(client):
    """Test that updating bookmark word recalculates position data."""
    # Create initial bookmark
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der große Hund bellt",
        sentence_i=0,
        token_i=2,  # "Hund" at position 2
        total_tokens=1
    )

    # Update the bookmark to a different word in same context
    # The backend should recalculate the position
    update_data = {
        "word": "große",  # Different word, position 1
        "translation": "big",
        "context": "Der große Hund bellt",
        "context_identifier": {
            "context_type": "ArticleFragment",
            "article_id": None,
            "context_id": None
        }
    }

    client.post(f"/update_bookmark/{bookmark_id}", json=update_data)

    # Verify positions were recalculated
    bookmark = Bookmark.find(bookmark_id)
    assert bookmark.user_word.meaning.origin.content == "große"
    # Position should be recalculated by validate_and_update_position()
    assert bookmark.token_i == 1, "Position should be recalculated to token 1"
    assert bookmark.sentence_i == 0
    assert bookmark.total_tokens == 1


def test_bookmark_update_with_context_change_recalculates_positions(client):
    """Test that updating context recalculates position data."""
    # Create initial bookmark
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt",
        sentence_i=0,
        token_i=1,
        total_tokens=1
    )

    # Update with new context where word is at different position
    update_data = {
        "word": "Hund",  # Same word
        "translation": "dog",
        "context": "Ein kleiner Hund läuft",  # "Hund" now at position 2
        "context_identifier": {
            "context_type": "ArticleFragment",
            "article_id": None,
            "context_id": None
        }
    }

    client.post(f"/update_bookmark/{bookmark_id}", json=update_data)

    # Verify positions were recalculated
    bookmark = Bookmark.find(bookmark_id)
    # Position should be recalculated by validate_and_update_position()
    assert bookmark.token_i == 2, "Position should be recalculated to new context position"
    assert bookmark.sentence_i == 0
    assert bookmark.total_tokens == 1


def test_multiword_update_recalculates_total_tokens(client):
    """Test that updating single word to multi-word updates total_tokens."""
    # Create single-word bookmark
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="nicht",
        context="Das ist nicht mehr möglich",
        sentence_i=0,
        token_i=2,
        total_tokens=1
    )

    # Update to multi-word phrase
    update_data = {
        "word": "nicht mehr",  # Now multi-word
        "translation": "no longer",
        "context": "Das ist nicht mehr möglich",
        "context_identifier": {
            "context_type": "ArticleFragment",
            "article_id": None,
            "context_id": None
        }
    }

    client.post(f"/update_bookmark/{bookmark_id}", json=update_data)

    # Verify total_tokens was updated
    bookmark = Bookmark.find(bookmark_id)
    assert bookmark.user_word.meaning.origin.content == "nicht mehr"
    assert bookmark.total_tokens == 2, "total_tokens should be updated to 2"
    assert bookmark.token_i == 2, "Position should remain at first token"


def test_no_null_positions_for_new_bookmarks(client):
    """Test that newly created bookmarks never have NULL position data."""
    # Create several bookmarks
    bookmark_ids = []

    test_cases = [
        ("der", "der neue Tag", 0, 0, 1),
        ("neue", "der neue Tag", 0, 1, 1),
        ("neue Tag", "der neue Tag beginnt", 0, 1, 2),  # Multi-word
    ]

    for word, context, sent_i, tok_i, total in test_cases:
        bid = _create_bookmark_with_positions(client, word, context, sent_i, tok_i, total)
        bookmark_ids.append(bid)

    # Verify none have NULL positions
    for bid in bookmark_ids:
        bookmark = Bookmark.find(bid)
        assert bookmark.sentence_i is not None, f"Bookmark {bid}: sentence_i should not be NULL"
        assert bookmark.token_i is not None, f"Bookmark {bid}: token_i should not be NULL"
        assert bookmark.total_tokens is not None, f"Bookmark {bid}: total_tokens should not be NULL"
        assert bookmark.total_tokens >= 1, f"Bookmark {bid}: total_tokens should be >= 1"


def test_word_expansion_workflow(client):
    """
    Test the frontend word expansion workflow:
    1. Translate single word "nicht"
    2. Expand to "nicht mehr" (frontend deletes old, creates new)

    This simulates the actual user behavior when extending translations in the reader.
    The delete+add approach is correct here because:
    - User is actively reading (no exercise history yet)
    - Happens within seconds of initial translation
    - Frontend needs to handle word fusion cleanly
    """
    add_context_types()
    add_source_types()

    # Create article
    from fixtures import create_and_get_article
    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_FRAGMENT, None, article["id"])

    context_text = "Das ist nicht mehr möglich"

    # Step 1: User translates "nicht" (single word at position 2)
    response1 = client.post(
        "/get_one_translation/de/en",
        json={
            "word": "nicht",
            "context": context_text,
            "source_id": article["source_id"],
            "w_sent_i": 0,
            "w_token_i": 2,
            "w_total_tokens": 1,
            "c_sent_i": 0,
            "c_token_i": 0,
            "context_identifier": context_i.as_dictionary(),
        },
    )

    bookmark_id_1 = response1["bookmark_id"]
    bookmark_1 = Bookmark.find(bookmark_id_1)

    # Verify first bookmark has correct position for single word
    assert bookmark_1.user_word.meaning.origin.content == "nicht"
    assert bookmark_1.sentence_i == 0
    assert bookmark_1.token_i == 2
    assert bookmark_1.total_tokens == 1

    # Step 2: User expands to "nicht mehr" (frontend deletes old, creates new)
    # Note: In real usage, frontend would call deleteBookmark but test client
    # doesn't handle empty responses well, so we'll just verify the new one works

    response2 = client.post(
        "/get_one_translation/de/en",
        json={
            "word": "nicht mehr",
            "context": context_text,
            "source_id": article["source_id"],
            "w_sent_i": 0,
            "w_token_i": 2,  # Still starts at position 2
            "w_total_tokens": 2,  # But spans 2 tokens now
            "c_sent_i": 0,
            "c_token_i": 0,
            "context_identifier": context_i.as_dictionary(),
        },
    )

    bookmark_id_2 = response2["bookmark_id"]
    bookmark_2 = Bookmark.find(bookmark_id_2)

    # Verify expanded bookmark has correct position data
    assert bookmark_2.user_word.meaning.origin.content == "nicht mehr"
    assert bookmark_2.sentence_i == 0, "sentence_i should be 0"
    assert bookmark_2.token_i == 2, "token_i should be at first token of phrase"
    assert bookmark_2.total_tokens == 2, "total_tokens should be 2 for multi-word phrase"

    # Verify position data is not NULL
    assert bookmark_2.sentence_i is not None
    assert bookmark_2.token_i is not None
    assert bookmark_2.total_tokens is not None
