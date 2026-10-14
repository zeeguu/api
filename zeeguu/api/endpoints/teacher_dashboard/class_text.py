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
    part with `lookups`: for every token some student translated, the students
    who did. The teacher's page colours the text by it, as a heatmap.

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
            **_text_with_lookups(article, bookmarks),
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


def _text_with_lookups(article, bookmarks):
    """
    The article's tokenized title and fragments, each with `lookups`:
    [{sent_i, token_i, students: [{id, translation}]}], one entry per token a
    student looked up, with the translation each of them got.
    """
    # part ("title" or a fragment id) -> (sent_i, token_i) -> {student id: translation}
    found = defaultdict(lambda: defaultdict(dict))
    part_of = _part_of_each(bookmarks)
    for bookmark in bookmarks:
        part = part_of.get(bookmark.id)
        if part is None:
            continue
        for position in _tokens_covered(bookmark):
            # looked up twice: their first translation stands
            found[part][position].setdefault(
                bookmark.user_word.user_id, bookmark.user_word.meaning.translation.content
            )

    def with_lookups(tokenized, part):
        return {
            **tokenized,
            "lookups": [
                {
                    "sent_i": sent_i,
                    "token_i": token_i,
                    "students": [{"id": id, "translation": t} for id, t in sorted(who.items())],
                }
                for (sent_i, token_i), who in sorted(found[part].items())
            ],
        }

    content = article.article_info(with_content=True)
    return {
        "tokenized_title_new": with_lookups(content.get("tokenized_title_new") or {}, "title"),
        "tokenized_fragments": [
            with_lookups(fragment, fragment["context_identifier"]["article_fragment_id"])
            for fragment in content.get("tokenized_fragments") or []
        ],
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


def _tokens_covered(bookmark):
    """
    The (sent_i, token_i) of every token the bookmark covers.

    Its position is its context's offset plus its own, the same sum the reader
    does (bookmarkRestoration.js). A phrase covers all its tokens; a separated
    multi-word expression only its two parts.
    """
    if bookmark.context is None:
        return []
    sent_i = (bookmark.context.sentence_i or 0) + (bookmark.sentence_i or 0)
    token_i = (bookmark.context.token_i or 0) + (bookmark.token_i or 0)
    if bookmark.is_mwe and bookmark.mwe_partner_token_i is not None:
        # the partner's index is already absolute (validateMweBookmark)
        return [(sent_i, token_i), (sent_i, bookmark.mwe_partner_token_i)]
    return [(sent_i, token_i + k) for k in range(bookmark.total_tokens or 1)]
