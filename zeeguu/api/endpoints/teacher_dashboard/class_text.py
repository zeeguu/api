from collections import defaultdict

import flask
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from zeeguu.core.model import Article, Cohort
from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
from zeeguu.core.model.article_title_context import ArticleTitleContext
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.meaning import Meaning
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

    The text itself comes too (tokenized_title_new, tokenized_fragments), each
    part with the class's bookmarks made in it. The teacher's page places them
    on the text and colours it by how many students looked each word up.

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
        # everything the three views below read, in this one query: lazily,
        # it was five queries per bookmark, and a class text has hundreds
        .options(
            joinedload(Bookmark.user_word).joinedload(UserWord.meaning).joinedload(Meaning.origin),
            joinedload(Bookmark.user_word).joinedload(UserWord.meaning).joinedload(Meaning.translation),
            joinedload(Bookmark.context).joinedload(BookmarkContext.text),
        )
        .order_by(Bookmark.time)
        .all()
    )
    opened = (
        UserArticle.query.filter(UserArticle.article_id == article.id)
        .filter(UserArticle.user_id.in_(students.keys()))
        .filter(UserArticle.opened.isnot(None))
        .all()
    )
    reading_ms_per_student = dict(
        db.session.query(UserReadingSession.user_id, func.sum(UserReadingSession.duration))
        .filter(UserReadingSession.article_id == article.id)
        .filter(UserReadingSession.user_id.in_(students.keys()))
        .group_by(UserReadingSession.user_id)
        .all()
    )

    title, fragments = _text_with_bookmarks(article, bookmarks)
    return json_result(
        {
            "article": {"id": article.id, "title": article.title},
            "student_count": len(students),
            "readers": _readers(students, opened, bookmarks, reading_ms_per_student),
            "words": _words(students, bookmarks),
            "tokenized_title_new": title,
            "tokenized_fragments": fragments,
        }
    )


def _readers(students, opened, bookmarks, reading_ms_per_student):
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
            "reading_seconds": round((reading_ms_per_student.get(user_id) or 0) / 1000),
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


def _text_with_bookmarks(article, bookmarks):
    """
    (title, fragments): the article's tokenized parts, each with `class_bookmarks`:
    the class's lookups made in that part, with the fields the reader needs to
    place a bookmark on its tokens, plus whose it is and what they got.

    The placing itself happens on the web, in bookmarkRestoration.js, the one
    place that knows how a bookmark's anchors combine.
    """
    in_part = defaultdict(list)
    part_of = _part_of_each(bookmarks)
    for bookmark in bookmarks:
        part = part_of.get(bookmark.id)
        if part is not None and bookmark.context is not None:
            in_part[part].append(_placeable(bookmark))

    content = article.article_info(with_content=True)
    title = content.get("tokenized_title_new") or {}
    return (
        {**title, "class_bookmarks": in_part["title"]},
        [
            {**fragment, "class_bookmarks": in_part[fragment["context_identifier"]["article_fragment_id"]]}
            for fragment in content.get("tokenized_fragments") or []
        ],
    )


def _placeable(bookmark):
    """A bookmark as the reader's restoration reads it, plus its student."""
    meaning = bookmark.user_word.meaning
    return {
        "student_id": bookmark.user_word.user_id,
        "origin": meaning.origin.content,
        "translation": meaning.translation.content,
        "context_sent": bookmark.context.sentence_i,
        "context_token": bookmark.context.token_i,
        "t_sentence_i": bookmark.sentence_i,
        "t_token_i": bookmark.token_i,
        "t_total_token": bookmark.total_tokens,
        "is_mwe": bool(bookmark.is_mwe),
        "mwe_partner_token_i": bookmark.mwe_partner_token_i,
    }


def _part_of_each(bookmarks):
    """{bookmark id: "title" or the id of the fragment it was made in}."""
    ids = [b.id for b in bookmarks]
    part_of = dict(
        db.session.query(ArticleFragmentContext.bookmark_id, ArticleFragmentContext.article_fragment_id)
        .filter(ArticleFragmentContext.bookmark_id.in_(ids))
        .all()
    )
    for (bookmark_id,) in (
        db.session.query(ArticleTitleContext.bookmark_id).filter(ArticleTitleContext.bookmark_id.in_(ids)).all()
    ):
        part_of[bookmark_id] = "title"
    return part_of
