"""A reader's correction of a translation reaches the next readers of the same
sentence: at once when a teacher made it, after the nightly validator run
when a learner did (TranslationCorrection)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from fixtures import LoggedInClient, add_context_types, add_source_types, create_and_get_article
from fixtures import logged_in_client as client
from zeeguu.core.model import Teacher, User
from zeeguu.core.model.db import db
from zeeguu.core.model.translation_correction import TranslationCorrection, corrections_to_judge, judge
from zeeguu.core.model.translation_service import TranslationService

WORD = "Haus"
SENTENCE = "Das Haus ist sehr alt und steht am Fluss"


@pytest.fixture
def machine():
    """The machine translators: always the same wrong answer."""
    with patch("zeeguu.api.endpoints.translation.IS_DEV_SKIP_TRANSLATION", False), patch(
        "zeeguu.api.endpoints.translation.get_best_translation",
        side_effect=lambda word, *a, **k: {"translation": "machine", "source": "Test", "likelihood": None},
    ) as translator:
        yield translator


@pytest.fixture
def article(client):
    add_source_types()
    add_context_types()
    return create_and_get_article(client)


def _look_up(reader, article, sentence=SENTENCE):
    return reader.post(
        "/get_one_translation/de/en",
        json={
            "word": WORD,
            "context": sentence,
            "source_id": article["source_id"],
            "w_sent_i": 0,
            "w_token_i": sentence.split().index(WORD),
            "w_total_tokens": 1,
            "c_sent_i": 0,
            "c_token_i": 0,
            "context_identifier": {"context_type": "ArticleFragment"},
        },
    )


def _correct(reader, article, translation):
    bookmark_id = _look_up(reader, article)["bookmark_id"]
    reader.post(f"/update_bookmark_translation/{bookmark_id}", json={"translation": translation})


def _other_reader(client, email="other@mir.lu"):
    return LoggedInClient(client.client, email=email, username="other")


def _make_teacher(reader):
    db.session.add(Teacher(User.find(reader.email)))
    db.session.commit()


def _validator(verdict):
    return SimpleNamespace(
        validate_translation=lambda **kw: SimpleNamespace(
            is_valid=verdict == "VALID", verdict=verdict, reason="because"
        )
    )


def test_a_teachers_correction_reaches_the_next_reader(client, article, machine):
    _make_teacher(client)
    _correct(client, article, "house")

    answer = _look_up(_other_reader(client), article)

    assert (answer["translation"], answer["source"]) == ("house", TranslationService.CORRECTION)


def test_a_learners_correction_waits_for_the_validator(client, article, machine):
    _correct(client, article, "house")
    other = _other_reader(client)

    assert _look_up(other, article)["translation"] == "machine"

    (pending,) = corrections_to_judge()
    assert judge(db.session, pending, _validator("VALID")) == "VALID"
    assert (pending.status, pending.accepted_by) == (TranslationCorrection.ACCEPTED, TranslationCorrection.VALIDATOR)
    third = _other_reader(client, email="third@mir.lu")
    assert _look_up(third, article)["translation"] == "house"


def test_a_correction_the_validator_rejects_stays_private(client, article, machine):
    _correct(client, article, "a typo")

    (pending,) = corrections_to_judge()
    judge(db.session, pending, _validator("FIX"))

    assert pending.status == TranslationCorrection.REJECTED
    assert _look_up(_other_reader(client), article)["translation"] == "machine"


def test_no_verdict_asks_again_the_next_night(client, article, machine):
    _correct(client, article, "house")
    (pending,) = corrections_to_judge()

    assert judge(db.session, pending, SimpleNamespace(validate_translation=lambda **kw: None)) is None
    assert corrections_to_judge() == [pending]


def test_a_teachers_correction_is_audited_not_overruled(client, article, machine):
    _make_teacher(client)
    _correct(client, article, "house")

    (audited,) = corrections_to_judge()
    judge(db.session, audited, _validator("FIX"))

    assert (audited.status, audited.verdict) == (TranslationCorrection.ACCEPTED, "FIX")
    assert corrections_to_judge() == []
    assert _look_up(_other_reader(client), article)["translation"] == "house"


def test_found_in_a_longer_or_shorter_version_of_the_sentence(client, article, machine):
    _make_teacher(client)
    _correct(client, article, "house")
    other = _other_reader(client)

    assert _look_up(other, article, "Gestern sagte er: " + SENTENCE + ", sagt man")["translation"] == "house"
    assert _look_up(_other_reader(client, "third@mir.lu"), article, "Das Haus ist sehr alt")["translation"] == "house"
    assert _look_up(_other_reader(client, "fourth@mir.lu"), article, "Ein Haus am See")["translation"] == "machine"


def test_correcting_again_replaces_the_earlier_correction(client, article, machine):
    _make_teacher(client)
    _correct(client, article, "home")
    _correct(client, article, "house")

    assert [c.translation for c in TranslationCorrection.query.all()] == ["house"]


def test_the_alternatives_menu_lists_the_correction_first(client, article, machine):
    _make_teacher(client)
    _correct(client, article, "house")

    with patch(
        "zeeguu.core.translation_services.translator._vote_translation",
        return_value={"alternatives": [{"translation": "machine", "source": "Test", "votes": 2}]},
    ):
        menu = _other_reader(client).post(
            "/translation_alternatives/de/en", json={"word": WORD, "context": SENTENCE}
        )["alternatives"]

    assert [a["translation"] for a in menu] == ["house", "machine"]


def test_an_admins_correction_counts_at_once(client, article, machine):
    user = User.find(client.email)
    user.is_admin = True
    db.session.commit()
    _correct(client, article, "house")

    assert _look_up(_other_reader(client), article)["translation"] == "house"
