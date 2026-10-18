"""Only the uploader of a text edits it, deletes it, or sets its CEFR level.

Everyone else is refused, and the article is left as it was."""

import json
import uuid
from unittest.mock import patch

import pytest

from fixtures import logged_in_client as client
from fixtures import LoggedInClient, add_context_types, add_source_types
from fixtures import create_and_get_article
from zeeguu.core.model import Article, User


@pytest.fixture
def other(client):
    return LoggedInClient(client.client, email="other@mir.lu", username="other")


@pytest.fixture
def text_id(client):
    add_source_types()
    add_context_types()
    new_id = client.post(
        "/upload_own_text",
        data=dict(
            title="Mein Text",
            # Uploads share the session-wide article table; the content
            # must be unique because it identifies the article's Source.
            content=f"Das ist mein Text {uuid.uuid4().hex}.",
            language="de",
            # Skips the LLM assessment on upload
            original_cefr_level="B1",
        ),
    )
    return int(new_id)


def _update(user_client, article_id, title):
    return user_client.response_from_post(
        f"/update_own_text/{article_id}",
        data=dict(title=title, content=f"Neuer Inhalt {uuid.uuid4().hex}.", language="de"),
    )


def _title(article_id):
    return Article.find_by_id(article_id).title


def _assessment(article_id):
    return Article.find_by_id(article_id).cefr_assessment


def _teacher_level(article_id):
    return _assessment(article_id).teacher_cefr_level


# --- update ---------------------------------------------------------------------


def test_owner_updates_own_text(client, text_id):
    response = _update(client, text_id, "Neuer Titel")
    assert response.status_code == 200
    assert _title(text_id) == "Neuer Titel"


def test_other_user_cannot_update_text(client, other, text_id):
    response = _update(other, text_id, "Fremder Titel")
    assert response.status_code == 403
    assert _title(text_id) == "Mein Text"


def test_nobody_can_update_a_crawled_article(client):
    add_source_types()
    add_context_types()
    article_id = create_and_get_article(client)["id"]
    title = _title(article_id)

    assert _update(client, article_id, "Fremder Titel").status_code == 403
    assert _title(article_id) == title


# --- delete ---------------------------------------------------------------------


def test_other_user_cannot_delete_text(client, other, text_id):
    for method in (other.client.get, other.client.post, other.client.delete):
        response = method(other.append_session(f"/delete_own_text/{text_id}"))
        assert response.status_code == 403

    article = Article.find_by_id(text_id)
    assert article is not None and not article.deleted


def test_owner_deletes_own_text_with_get(client, text_id):
    # Older clients still delete with GET
    result = client.get(f"/delete_own_text/{text_id}")
    assert result["success"] is True
    assert Article.find_by_id(text_id) is None


def test_owner_deletes_own_text_with_post(client, text_id):
    result = client.post(f"/delete_own_text/{text_id}")
    assert result["success"] is True
    assert Article.find_by_id(text_id) is None


# --- CEFR level -----------------------------------------------------------------


def test_owner_resolves_cefr_of_own_text(client, text_id):
    result = client.post(f"/article/{text_id}/resolve_cefr", data=dict(cefr_level="A2"))
    assert result["resolved_level"] == "A2"
    assert _teacher_level(text_id) == "A2"


def test_other_user_cannot_resolve_cefr(client, other, text_id):
    response = other.response_from_post(
        f"/article/{text_id}/resolve_cefr", data=dict(cefr_level="C2")
    )
    assert response.status_code == 403
    assert _teacher_level(text_id) is None


def test_other_user_cannot_store_cefr_assessment(client, other, text_id):
    response = other.response_from_post(
        f"/article/{text_id}/store_cefr_assessment",
        data=dict(cefr_level="C2", assessment_method="teacher_manual"),
    )
    assert response.status_code == 403
    assert _teacher_level(text_id) is None


def test_stored_assessment_is_attributed_to_the_caller(client, other, text_id):
    other_id = User.find(other.email).id
    result = client.post(
        f"/article/{text_id}/store_cefr_assessment",
        data=dict(
            cefr_level="A2",
            assessment_method="teacher_manual",
            assessed_by_user_id=other_id,
        ),
    )
    assert result["status"] == "success"

    assessment = _assessment(text_id)
    assert assessment.teacher_cefr_level == "A2"
    assert assessment.teacher_assessed_by_user_id == User.find(client.email).id


# --- estimate -------------------------------------------------------------------


def test_estimate_does_not_reveal_server_paths(client, monkeypatch):
    monkeypatch.setenv("ZEEGUU_DATA_FOLDER", "/srv/secret-data")
    with patch(
        "zeeguu.api.endpoints.article_cefr_recompute.compute_ml_assessment",
        return_value=(None, None),
    ):
        response = client.response_from_post(
            "/estimate_article_cefr", data=dict(content="Hallo Welt.", language="de")
        )

    assert response.status_code == 200
    assert "/srv/secret-data" not in response.data.decode()
    result = json.loads(response.data)
    assert result["cefr_level"] is None
    assert result["debug"]["language_code"] == "de"
