from unittest.mock import patch

from fixtures import (
    logged_in_client as client,
    add_one_bookmark,
    add_context_types,
    add_source_types,
)

from zeeguu.core.llm_services.cloze_alternative_judge import ClozeAlternativeVerdict


class _Judge:
    MODEL_NAME = "fake-judge"

    def judge(self, **kwargs):
        return ClozeAlternativeVerdict("SYNONYM", False, "")


def test_judges_a_word_typed_into_the_learners_own_cloze(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)  # hinter -> behind

    with patch("zeeguu.core.llm_services.cloze_alternative_judge.ClozeAlternativeJudge", _Judge):
        result = client.post("judge_cloze_alternative", json={"bookmark_id": bookmark_id, "typed": "hinten"})

    assert result == {"relation": "SYNONYM", "explanation": "", "cached": False}


def test_refuses_a_bookmark_of_another_learner(client, app):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)

    from fixtures import LoggedInClient

    stranger = LoggedInClient(app.test_client(), email="stranger@mir.lu", username="stranger")
    response = stranger.response_from_post(
        "judge_cloze_alternative", json={"bookmark_id": bookmark_id, "typed": "hinten"}
    )

    assert response.status_code == 404


def test_requires_the_typed_word(client):
    response = client.response_from_post("judge_cloze_alternative", json={"bookmark_id": 1})
    assert response.status_code == 400


def test_judges_a_translation_typed_for_the_learners_word(client):
    add_context_types()
    add_source_types()
    bookmark_id = add_one_bookmark(client)  # hinter -> behind

    with patch("zeeguu.core.llm_services.translation_alternative_judge.TranslationAlternativeJudge", _Judge):
        result = client.post("judge_translation_alternative", json={"bookmark_id": bookmark_id, "typed": "after"})

    assert result == {"relation": "SYNONYM", "explanation": "", "cached": False}


def test_a_typed_translation_requires_the_typed_text(client):
    response = client.response_from_post("judge_translation_alternative", json={"bookmark_id": 1})
    assert response.status_code == 400
