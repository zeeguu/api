import flask
from sqlalchemy import func

from zeeguu.core.model import Article, Cohort
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_word import UserWord
from ._only_teachers_decorator import only_teachers
from ._permissions import check_permission_for_cohort
from .. import api
from zeeguu.api.utils import json_result, requires_session


@api.route("/class_text/<int:cohort_id>/<int:article_id>", methods=["GET"])
@requires_session
@only_teachers
def class_text(cohort_id, article_id):
    """
    One text, as a whole class read it: who opened it, and the words they
    looked up in it, the ones most students needed first.

    For the teachers who give a class one text at a time: a word half the
    class translated is one to go over in the lesson.

    Only the class's own students count, so a text shared with two classes
    reports each separately.
    """
    check_permission_for_cohort(cohort_id)
    cohort = Cohort.find(cohort_id)
    article = Article.find_by_id(article_id)
    if not article:
        flask.abort(404)

    students = {student.id: student for student in cohort.get_students()}

    bookmarks = (
        Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
        .filter(Bookmark.source_id == article.source_id)
        .filter(UserWord.user_id.in_(students.keys()))
        .order_by(Bookmark.time)
        .all()
    )
    opened = (
        UserArticle.query.filter(UserArticle.article_id == article.id)
        .filter(UserArticle.user_id.in_(students.keys()))
        .filter(UserArticle.opened.isnot(None))
        .all()
    )
    milliseconds = dict(
        db.session.query(UserReadingSession.user_id, func.sum(UserReadingSession.duration))
        .filter(UserReadingSession.article_id == article.id)
        .filter(UserReadingSession.user_id.in_(students.keys()))
        .group_by(UserReadingSession.user_id)
        .all()
    )

    return json_result(
        {
            "article": {"id": article.id, "title": article.title},
            "student_count": len(students),
            "readers": _readers(students, opened, bookmarks, milliseconds),
            "words": _words(students, bookmarks),
        }
    )


def _readers(students, opened, bookmarks, milliseconds):
    """Every student who opened the text, or translated in it, furthest read first."""
    completion = {each.user_id: each.reading_completion or 0 for each in opened}
    translations = {}
    for bookmark in bookmarks:
        user_id = bookmark.user_word.user_id
        translations[user_id] = translations.get(user_id, 0) + 1

    readers = [
        {
            "id": user_id,
            "name": students[user_id].name,
            "reading_completion": completion.get(user_id, 0),
            "reading_seconds": round((milliseconds.get(user_id) or 0) / 1000),
            "translations": translations.get(user_id, 0),
        }
        for user_id in set(completion) | set(translations)
    ]
    return sorted(readers, key=lambda r: (-r["reading_completion"], r["name"] or ""))


def _words(students, bookmarks):
    """
    The words looked up, grouped across students, the most-needed first.

    The same word is one entry however many times, and however differently,
    it was translated; a student who looked it up twice counts once.
    """
    words = {}
    for bookmark in bookmarks:
        meaning = bookmark.user_word.meaning
        key = meaning.origin.content.lower()
        word = words.setdefault(
            key,
            {
                "word": meaning.origin.content,
                "translations": [],
                "students": [],
                "context": bookmark.get_context(),
            },
        )
        if meaning.translation.content not in word["translations"]:
            word["translations"].append(meaning.translation.content)
        user_id = bookmark.user_word.user_id
        if user_id not in [s["id"] for s in word["students"]]:
            word["students"].append({"id": user_id, "name": students[user_id].name})

    return sorted(words.values(), key=lambda w: (-len(w["students"]), w["word"].lower()))
