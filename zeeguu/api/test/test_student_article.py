from fixtures import logged_in_teacher as client
from fixtures import add_context_types, add_source_types, create_and_get_article
from zeeguu.core.model import User
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA

GERMAN_CLASS = {"inv_code": "de123", "name": "German", "language_id": "de", "max_students": 10}


def _join(client, email):
    data = dict(password="test", username=email, learned_language="de", invite_code="de123")
    session = client.client.post(f"/add_user/{email}", data=data).data.decode("utf-8")
    return User.find(email), session


def test_teacher_sees_the_article_with_the_students_translations(client):
    add_source_types()
    add_context_types()
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    student, session = _join(client, "student@mir.lu")
    article = create_and_get_article(client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    client.client.post(
        f"/contribute_translation/de/en?session={session}",
        json={
            "word": "hinter",
            "translation": "behind",
            "context": "stellt sich hinter Präsident",
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )

    # the student opened it, as reading does (the reader's bookmarks are
    # attached for an article the reader has opened)
    from datetime import datetime
    from zeeguu.core.model import Article
    from zeeguu.core.model.db import db
    from zeeguu.core.model.user_article import UserArticle

    student = User.find("student@mir.lu")
    db.session.add(UserArticle(student, Article.find_by_id(article["id"]), opened=datetime.now()))
    db.session.commit()

    info = client.get(f"/student_article/{article['id']}?student_id={student.id}&cohort_id=1")

    past = info["tokenized_title_new"]["past_bookmarks"]
    assert [b["from"] for b in past] == ["hinter"]


def test_only_the_classes_teacher(client):
    client.post("/create_own_cohort", data=GERMAN_CLASS)
    student, _ = _join(client, "student@mir.lu")
    _, mate = _join(client, "mate@mir.lu")
    url = f"/student_article/1?student_id={student.id}&cohort_id=1&session={mate}"
    assert client.client.get(url).status_code == 401
