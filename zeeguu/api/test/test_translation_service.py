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


def _add_learning_card(client, example):
    card = {"word": "hinter", "translation": "behind", "example": example, "example_translation": "-"}
    with patch("zeeguu.api.endpoints.generated_examples.prepare_learning_card", return_value=card):
        return client.post(
            "/add_word_to_learning",
            json={"word": "hinter", "translation": "behind", "from_lang": "de", "to_lang": "en"},
        )


def test_a_learning_card_is_scheduled_with_its_example(client):
    from zeeguu.core.word_scheduling import BasicSRSchedule
    from zeeguu.core.model import UserWord

    add_context_types()
    add_source_types()
    result = _add_learning_card(client, "stellt sich hinter Präsident")
    bookmark = Bookmark.find(result["bookmark_id"])
    assert _service(bookmark.id) == TranslationService.LEARNING_CARD
    assert bookmark.context.get_content() == "stellt sich hinter Präsident"
    user_word = UserWord.query.get(result["user_word_id"])
    assert user_word.is_user_added and user_word.level == 1
    assert BasicSRSchedule.find(user_word)


def test_a_learning_card_whose_example_lacks_the_word_keeps_the_word_alone(client):
    add_context_types()
    add_source_types()
    result = _add_learning_card(client, "stellt sich vor Präsident")
    assert Bookmark.find(result["bookmark_id"]).context.get_content() == "hinter"


def test_a_chosen_alternative_records_its_service_when_the_client_sends_it(client):
    from zeeguu.core.model import db

    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    TranslationService.find_or_create(db.session, "Microsoft")
    db.session.commit()
    client.post(f"/update_bookmark_translation/{bookmark_id}",
                json={"translation": "after", "translation_service": "Microsoft"})
    assert _service(bookmark_id) == "Microsoft"


def test_a_client_cannot_invent_services(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    services_before = TranslationService.query.count()
    client.post(f"/update_bookmark_translation/{bookmark_id}",
                json={"translation": "after", "translation_service": "made up"})
    assert _service(bookmark_id) == TranslationService.CHOSEN_ALTERNATIVE
    # CHOSEN_ALTERNATIVE itself is the only new row
    assert TranslationService.query.count() == services_before + 1

    response = client.client.post(
        client.append_session(f"/update_bookmark_translation/{bookmark_id}"),
        json={"translation": "before", "translation_service": 123},
    )
    assert response.status_code == 200
    assert _service(bookmark_id) == TranslationService.CHOSEN_ALTERNATIVE


def test_a_contributed_translation_with_a_null_service_is_manual(client):
    add_context_types()
    add_source_types()
    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    result = client.post(
        "/contribute_translation/de/en",
        json={"word": "hinter", "translation": "behind", "context": "stellt sich hinter Präsident",
              "source_id": article["source_id"], "context_identifier": context_i.as_dictionary(),
              "servicename_translation": None},
    )
    assert _service(result["bookmark_id"]) == TranslationService.MANUAL


def test_editing_only_the_word_makes_the_pair_manual(client):
    from zeeguu.core.model import db

    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    Bookmark.find(bookmark_id).set_translation_service(db.session, "DeepL")
    db.session.commit()
    client.post(f"/update_bookmark/{bookmark_id}",
                json={"word": "sich", "translation": "behind", "context": "stellt sich hinter Präsident",
                      "context_identifier": {"context_type": "ArticleTitle"}})
    assert _service(bookmark_id) == TranslationService.MANUAL


def test_a_chosen_alternative_from_an_older_client_is_still_marked(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    client.post(f"/update_bookmark_translation/{bookmark_id}", json={"translation": "after"})
    assert _service(bookmark_id) == TranslationService.CHOSEN_ALTERNATIVE



def _contribute(client, **extra):
    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    return client.client.post(
        client.append_session("/contribute_translation/de/en"),
        json={"word": "hinter", "translation": "behind", "context": "stellt sich hinter Präsident",
              "source_id": article["source_id"], "context_identifier": context_i.as_dictionary(), **extra},
    )


def test_a_contributed_translation_cannot_invent_or_claim_services(client):
    import json

    add_context_types()
    add_source_types()
    for claimed in ("made up", 5, {"a": 1}, TranslationService.VALIDATOR):
        response = _contribute(client, servicename_translation=claimed)
        assert response.status_code == 200
        assert _service(json.loads(response.data)["bookmark_id"]) == TranslationService.MANUAL
    assert TranslationService.query.filter_by(name="made up").count() == 0


def test_an_alternative_cannot_claim_an_internal_service(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)  # creates the MANUAL row
    client.post(f"/update_bookmark_translation/{bookmark_id}",
                json={"translation": "after", "translation_service": TranslationService.MANUAL})
    assert _service(bookmark_id) == TranslationService.CHOSEN_ALTERNATIVE


def test_a_bookmark_from_before_services_learns_its_service_when_found_again(client):
    from zeeguu.core.model import db

    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)
    bookmark = Bookmark.find(bookmark_id)
    bookmark.translation_service_id = None
    db.session.add(bookmark)
    db.session.commit()
    assert _service(add_one_bookmark(client)) == TranslationService.MANUAL
    assert _service(bookmark_id) == TranslationService.MANUAL
