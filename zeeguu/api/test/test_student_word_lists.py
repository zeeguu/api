from datetime import datetime

from fixtures import logged_in_teacher as client
from fixtures import add_context_types, add_source_types, create_and_get_article
from zeeguu.core.model import User
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.db import db
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA
from zeeguu.core.test.rules.exercise_source_rule import ExerciseSourceRule
from zeeguu.core.test.rules.scheduler_rule import SchedulerRule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

GERMAN_CLASS = {"inv_code": "de123", "name": "German", "language_id": "de", "max_students": 10}


def _join(client, email):
    data = dict(password="test", username=email, learned_language="de", invite_code="de123")
    session = client.client.post(f"/add_user/{email}", data=data).data.decode("utf-8")
    return User.find(email), session


def _translate(client, session, article, word, translation):
    """A translation as the reader makes it, so the word is anchored in its
    sentence (the Words pages drop words that aren't)."""
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    response = client.client.post(
        f"/contribute_translation/de/en?session={session}",
        json={
            "word": word,
            "translation": translation,
            "context": "stellt sich hinter Präsident",
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )
    return response.get_json()["bookmark_id"]


def test_teacher_sees_the_students_word_lists(client):
    add_source_types()
    add_context_types()
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    student, session = _join(client, "student@mir.lu")
    article = create_and_get_article(client)

    bookmark_ids = [
        _translate(client, session, article, "hinter", "behind"),
        _translate(client, session, article, "stellt", "puts"),
        _translate(client, session, article, "Präsident", "president"),
    ]
    # loaded after the requests, which end the session they ran in
    scheduled, excluded, learned = [Bookmark.find(b).user_word for b in bookmark_ids]

    scheduled.fit_for_study = 1
    # already validated, as every scheduled word is: scheduling would ask an LLM
    scheduled.meaning.validated = Meaning.VALID
    SchedulerRule(FourLevelsPerWord, scheduled, db.session)
    db.session.add(
        Exercise(
            ExerciseOutcome.find_or_create(db.session, "C"),
            ExerciseSourceRule().random,
            1000,
            datetime.now(),
            None,
            scheduled,
        )
    )
    excluded.fit_for_study = 0
    learned.learned_time = datetime.now()
    db.session.commit()
    ids = dict(scheduled=scheduled.id, excluded=excluded.id, learned=learned.id)

    lists = client.get(f"/student_word_lists?student_id={student.id}&cohort_id=1")

    assert [w["user_word_id"] for w in lists["scheduled"]] == [ids["scheduled"]]
    assert [a["outcome"] for a in lists["scheduled"][0]["exercise_attempts"]] == ["C"]
    assert [w["user_word_id"] for w in lists["excluded"]] == [ids["excluded"]]
    assert [w["user_word_id"] for w in lists["learned"]] == [ids["learned"]]
    assert lists["total_learned"] == 1


def test_only_the_classes_teacher_sees_them(client):
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    student, _ = _join(client, "student@mir.lu")
    _, classmate_session = _join(client, "mate@mir.lu")

    url = f"/student_word_lists?student_id={student.id}&cohort_id=1&session={classmate_session}"
    assert client.client.get(url).status_code == 401


def test_the_learners_own_word_pages_still_answer(client):
    # their endpoints now share the teacher view's helpers
    add_source_types()
    add_context_types()
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    _, session = _join(client, "learner@mir.lu")
    article = create_and_get_article(client)
    learned = Bookmark.find(_translate(client, session, article, "Präsident", "president")).user_word
    learned.learned_time = datetime.now()
    db.session.commit()

    def get(endpoint):
        return client.client.get(f"{endpoint}?session={session}").get_json()

    assert get("/all_scheduled_user_words") == []
    assert isinstance(get("/user_words_next_in_learning"), list)
    assert [w["from"] for w in get("/learned_user_words/10")] == ["Präsident"]
    assert get("/total_learned_user_words") == 1
