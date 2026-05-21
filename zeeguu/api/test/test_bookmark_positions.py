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


def test_as_dictionary_corrects_stale_anchor(client):
    """
    Issue #618 family: the stored (token_i, total_tokens) drifted out of sync
    with the tokenizer used to ship `context_tokenized` (different tokenizer
    version, or tokens were computed against an earlier text revision). The
    serialization-time correction in Bookmark.as_dictionary should detect the
    mismatch and serve a corrected anchor.
    """
    # Deliberately store a wrong token_i: word is "Hund" (position 1) but we
    # pretend the client claimed it was at position 0 ("Der").
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt laut",
        sentence_i=0,
        token_i=0,  # WRONG — "Hund" is at index 1, not 0
        total_tokens=1,
    )

    bookmark = Bookmark.find(bookmark_id)
    # DB row keeps the stored (wrong) values — fix is response-shaping only.
    assert bookmark.token_i == 0

    served = bookmark.as_dictionary(with_context=True, with_context_tokenized=True)
    # Response should carry the corrected position so the frontend can
    # highlight the right token.
    assert served["t_token_i"] == 1, (
        f"Served anchor should be corrected to point at 'Hund' (token 1), "
        f"got {served['t_token_i']}"
    )
    assert served["t_total_token"] == 1


def test_as_dictionary_preserves_correct_anchor_when_word_repeats(client):
    """
    When the same word appears multiple times in the context, the user's
    actual click position must be preserved — the correction must NOT
    indiscriminately snap to the first occurrence.
    """
    # "Hund" appears at positions 1 and 4 — the user clicked the second one.
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund sah einen Hund",
        sentence_i=0,
        token_i=4,
        total_tokens=1,
    )

    bookmark = Bookmark.find(bookmark_id)
    served = bookmark.as_dictionary(with_context=True, with_context_tokenized=True)
    assert served["t_token_i"] == 4, (
        f"Correct anchor should be preserved when word repeats; "
        f"got {served['t_token_i']}"
    )


def test_as_dictionary_marks_unanchorable_when_phrase_missing(client):
    """
    When `from` cannot be located contiguously in the tokenized context
    (e.g. discontiguous IDIOM — issue #618 bookmark 703020 family), the
    served bookmark dict is flagged `_unanchorable: True` so list-returning
    endpoints can drop it before sending to the frontend.
    """
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt laut",
        sentence_i=0,
        token_i=1,
        total_tokens=1,
    )

    # Re-point this bookmark to a meaning whose origin phrase is
    # non-contiguous in the context (mirrors the production
    # discontiguous-idiom shape).
    from zeeguu.core.model import Meaning
    from zeeguu.core.model.db import db as _db
    bookmark = Bookmark.find(bookmark_id)
    new_meaning = Meaning.find_or_create(
        _db.session, "Hund laut bellt", "de", "loud-dog-barks", "en"
    )
    _db.session.commit()
    bookmark.user_word.meaning_id = new_meaning.id
    _db.session.add(bookmark.user_word)
    _db.session.commit()

    served = bookmark.as_dictionary(with_context=True, with_context_tokenized=True)
    assert served.get("_unanchorable") is True, (
        "Bookmark with non-contiguous from-phrase should be marked unanchorable"
    )


def test_as_dictionary_serves_relative_anchor_when_context_offset_nonzero(client):
    """
    Regression: served `t_sentence_i` / `t_token_i` are RELATIVE to the
    bookmark's context (the frontend does `context_sent + t_sentence_i`
    to recover an absolute lookup key). When `context.sentence_i > 0`
    the correction must NOT serve the absolute sent_i from
    context_tokenized — that double-shifts on the frontend and the
    highlight disappears (bookmark 743773 prod symptom).
    """
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt laut",
        sentence_i=0,
        token_i=1,
        total_tokens=1,
    )

    from zeeguu.core.model.db import db as _db
    bookmark = Bookmark.find(bookmark_id)
    # Force the bookmark's context to start at sent_i=2 of its article.
    # tokenize_for_reading will then emit tokens with sent_i=2.
    bookmark.context.sentence_i = 2
    _db.session.add(bookmark.context)
    _db.session.commit()

    served = bookmark.as_dictionary(with_context=True, with_context_tokenized=True)
    # The stored anchor (sentence_i=0, token_i=1) was already correct in
    # the relative frame, so the served values must match — NOT 2 (the
    # absolute sent_i in context_tokenized).
    assert served["t_sentence_i"] == 0, (
        f"Expected relative t_sentence_i=0, got {served['t_sentence_i']} "
        f"(symptom: frontend would double-shift via context_sent)"
    )
    assert served["t_token_i"] == 1
    assert served["t_total_token"] == 1
    assert served["context_sent"] == 2  # context's own offset, unchanged


def test_as_dictionary_rotates_preferred_when_sibling_is_anchorable(client):
    """
    Preferred bookmark is unanchorable, but the user_word has another
    bookmark whose `from` IS locatable in its context. Self-heal should
    rotate preferred_bookmark to the sibling and KEEP the user_word fit
    for study.
    """
    # Bookmark A: word "Hund" but context doesn't contain it — unanchorable.
    bid_a = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Die Katze schläft.",
        sentence_i=0,
        token_i=1,
        total_tokens=1,
    )
    # Bookmark B: same word, context that DOES contain it — anchorable.
    bid_b = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt laut",
        sentence_i=0,
        token_i=1,
        total_tokens=1,
    )

    from zeeguu.core.model.db import db as _db
    bookmark_a = Bookmark.find(bid_a)
    # Sanity: both bookmarks land on the same user_word and A is preferred
    # (it was created first, so find_or_create picked it).
    assert bookmark_a.user_word.preferred_bookmark_id == bid_a
    assert Bookmark.find(bid_b).user_word_id == bookmark_a.user_word_id

    bookmark_a.as_dictionary(with_context=True, with_context_tokenized=True)

    _db.session.refresh(bookmark_a.user_word)
    assert bookmark_a.user_word.preferred_bookmark_id == bid_b, (
        "preferred_bookmark should rotate to the anchorable sibling"
    )
    assert bookmark_a.user_word.fit_for_study, (
        "user_word should stay fit_for_study after a successful rotation"
    )


def test_as_dictionary_unschedules_preferred_when_unanchorable(client):
    """
    When the user_word's PREFERRED bookmark can't be anchored, set the
    user_word not_fit_for_study so it stops being served into exercises.
    Self-heals existing broken rows without a separate sweep job.
    """
    bookmark_id = _create_bookmark_with_positions(
        client,
        word="Hund",
        context="Der Hund bellt laut",
        sentence_i=0,
        token_i=1,
        total_tokens=1,
    )

    from zeeguu.core.model import Meaning
    from zeeguu.core.model.db import db as _db
    bookmark = Bookmark.find(bookmark_id)
    # Pre-condition: this bookmark IS the preferred one for its user_word
    # and the user_word is fit for study.
    assert bookmark.user_word.preferred_bookmark_id == bookmark.id
    assert bookmark.user_word.fit_for_study

    # Promote the meaning to a phrase that doesn't fit contiguously.
    new_meaning = Meaning.find_or_create(
        _db.session, "Hund laut bellt", "de", "loud-dog-barks", "en"
    )
    _db.session.commit()
    bookmark.user_word.meaning_id = new_meaning.id
    _db.session.add(bookmark.user_word)
    _db.session.commit()

    # Serving with context_tokenized triggers the unschedule side-effect.
    bookmark.as_dictionary(with_context=True, with_context_tokenized=True)

    _db.session.refresh(bookmark.user_word)
    assert bookmark.user_word.fit_for_study is False, (
        "user_word should be marked not_fit_for_study after serving an "
        "unanchorable preferred bookmark"
    )


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
