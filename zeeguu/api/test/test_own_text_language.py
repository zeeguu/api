"""An own text in a language Zeeguu does not know is refused, not a 500."""

import uuid

from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types


def _upload(client, language):
    add_source_types()
    add_context_types()
    return client.response_from_post(
        "/upload_own_text",
        data=dict(
            title="Oma teksti",
            content=f"Tämä on minun tekstini {uuid.uuid4().hex}.",
            language=language,
            # Skips the LLM assessment on upload
            original_cefr_level="B1",
        ),
    )


def test_upload_in_unknown_language_is_refused(client):
    assert _upload(client, "fi").status_code == 406


def test_upload_without_language_is_refused(client):
    assert _upload(client, "").status_code == 406
