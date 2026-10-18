"""Every bookmark records who produced its translation, so a pair found broken
later can be traced to the engine that made it."""
from unittest.mock import patch

from fixtures import (
    logged_in_client as client,
    add_context_types,
    add_source_types,
    add_one_bookmark,
    create_and_get_article,
)
from zeeguu.core.model import Bookmark, TranslationService
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType


def _service(bookmark_id):
    service = Bookmark.find(bookmark_id).translation_service
    return service.name if service else None


def test_a_lookup_records_the_winning_service(client):
    add_context_types()
    add_source_types()
    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    with patch("zeeguu.api.endpoints.translation.IS_DEV_SKIP_TRANSLATION", False), patch(
        "zeeguu.api.endpoints.translation.get_best_translation",
        return_value={"translation": "behind", "source": "DeepL", "likelihood": 90},
    ):
        result = client.post(
            "/get_one_translation/de/en",
            json={
                "word": "hinter",
                "context": "stellt sich hinter Präsident",
                "source_id": article["source_id"],
                "context_identifier": context_i.as_dictionary(),
            },
        )
    assert _service(result["bookmark_id"]) == "DeepL"


def test_a_contributed_translation_without_a_service_is_manual(client):
    add_context_types()
    add_source_types()
    assert _service(add_one_bookmark(client)) == TranslationService.MANUAL


def test_a_custom_word_is_manual(client):
    add_context_types()
    add_source_types()
    result = client.post(
        "/add_custom_word",
        json={"word": "hinter", "translation": "behind", "from_lang": "de", "to_lang": "en",
              "context": "stellt sich hinter Präsident"},
    )
    assert _service(result["bookmark_id"]) == TranslationService.MANUAL


def test_a_chosen_alternative_records_its_service_when_the_client_sends_it(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    client.post(f"/update_bookmark_translation/{bookmark_id}",
                json={"translation": "after", "translation_service": "Microsoft"})
    assert _service(bookmark_id) == "Microsoft"


def test_a_chosen_alternative_from_an_older_client_is_still_marked(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    client.post(f"/update_bookmark_translation/{bookmark_id}", json={"translation": "after"})
    assert _service(bookmark_id) == TranslationService.CHOSEN_ALTERNATIVE

