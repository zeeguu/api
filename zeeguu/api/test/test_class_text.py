from fixtures import logged_in_teacher as client
from fixtures import add_context_types, add_source_types, create_and_get_article
from zeeguu.core.model import User
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA

GERMAN_CLASS = {"inv_code": "de123", "name": "German", "language_id": "de", "max_students": 10}


def _join(client, email, invite_code="de123"):
    data = dict(password="test", username=email, learned_language="de", invite_code=invite_code)
    return client.client.post(f"/add_user/{email}", data=data).data.decode("utf-8")


def _translate(client, session, article, word, translation):
    # where the word sits in "stellt sich hinter Präsident"
    token_i = {"hinter": 2, "Präsident": 3}[word]
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    client.client.post(
        f"/contribute_translation/de/en?session={session}",
        json={
            "word": word,
            "translation": translation,
            "context": "stellt sich hinter Präsident",
            "w_sent_i": 0,
            "w_token_i": token_i,
            "w_total_tokens": 1,
            "c_sent_i": 0,
            "c_token_i": 0,
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )


def test_the_words_most_students_needed_come_first(client):
    add_source_types()
    add_context_types()
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    max_session = _join(client, "max@mir.lu")
    ana_session = _join(client, "ana@mir.lu")
    article = create_and_get_article(client)
    _translate(client, max_session, article, "Präsident", "president")
    _translate(client, max_session, article, "hinter", "behind")
    _translate(client, ana_session, article, "hinter", "after")

    info = client.get(f"/class_text/1/{article['id']}")

    assert [w["word"] for w in info["words"]] == ["hinter", "Präsident"]
    hinter = info["words"][0]
    assert sorted(s["id"] for s in hinter["students"]) == sorted(
        [User.find("max@mir.lu").id, User.find("ana@mir.lu").id]
    )
    assert hinter["translations"] == ["behind", "after"]
    assert hinter["context"] == "stellt sich hinter Präsident"
    assert info["student_count"] == 2
    # the title's tokens come with who looked each up, for the heatmap
    title = info["tokenized_title_new"]
    assert title["tokens"]
    counts = {(l["sent_i"], l["token_i"]): len(l["students"]) for l in title["lookups"]}
    assert counts == {(0, 2): 2, (0, 3): 1}
    hinter_token = next(l for l in title["lookups"] if l["token_i"] == 2)
    assert sorted(s["translation"] for s in hinter_token["students"]) == ["after", "behind"]
    assert {r["id"]: r["translations"] for r in info["readers"]} == {
        User.find("max@mir.lu").id: 2,
        User.find("ana@mir.lu").id: 1,
    }


def test_students_of_other_classes_do_not_count(client):
    add_source_types()
    add_context_types()
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    client.post("/create_own_cohort", data={**GERMAN_CLASS, "inv_code": "de456", "name": "Other"})
    outsider = _join(client, "outsider@mir.lu", invite_code="de456")
    article = create_and_get_article(client)
    _translate(client, outsider, article, "hinter", "behind")

    info = client.get(f"/class_text/1/{article['id']}")

    assert info["words"] == []
    assert info["readers"] == []


def test_only_the_classes_teacher(client):
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    student = _join(client, "student@mir.lu")
    assert client.client.get(f"/class_text/1/1?session={student}").status_code == 401
