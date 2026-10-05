"""
All-time totals shown on the public research page (zeeguu.org/research).

Each number has exactly one definition, here, so the page cannot drift into
counting things it should not. Every count leaves out accounts marked is_dev
(the team's own and test accounts).

A *teacher* is not anyone who owns a class: over a hundred accounts do, most of
whom tried the dashboard and never had a class read anything. A teacher here
owns at least one class in which MIN_ACTIVE_STUDENTS students have each read at
least MIN_READING_SESSIONS times. Those classes are the *classes* counted.

Two kinds of cohort are not classes. A cohort of teachers: joining one is how
a new account becomes a teacher, so its members are teachers signing up. And a
study (is_study): a beta test, usability test or thesis experiment, whose
members still count as learners.
"""

from sqlalchemy import func, distinct

from zeeguu.core.model import User, Language, Article
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap
from zeeguu.core.model.user_cohort_map import UserCohortMap
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_word import UserWord

MIN_ACTIVE_STUDENTS = 5
MIN_READING_SESSIONS = 5

_not_dev = func.coalesce(User.is_dev, False) == False  # noqa: E712


def _lookups(session):
    return (
        session.query(func.count(Bookmark.id))
        .join(UserWord, Bookmark.user_word_id == UserWord.id)
        .join(User, UserWord.user_id == User.id)
        .filter(_not_dev)
        .scalar()
    )


def _exercises(session):
    return (
        session.query(func.count(Exercise.id))
        .join(UserWord, Exercise.user_word_id == UserWord.id)
        .join(User, UserWord.user_id == User.id)
        .filter(_not_dev)
        .scalar()
    )


def _learners(session):
    """Accounts that looked up at least one word."""
    return (
        session.query(func.count(distinct(UserWord.user_id)))
        .join(Bookmark, Bookmark.user_word_id == UserWord.id)
        .join(User, UserWord.user_id == User.id)
        .filter(_not_dev)
        .scalar()
    )


def _articles(session, language_ids):
    """Readable articles in the languages we offer."""
    return (
        session.query(func.count(Article.id))
        .filter(Article.language_id.in_(language_ids))
        .filter(func.coalesce(Article.broken, 0) == 0)
        .filter(func.coalesce(Article.deleted, 0) == 0)
        .scalar()
    )


def _teachers_and_classes(session):
    readers = (
        session.query(UserReadingSession.user_id)
        .join(User, UserReadingSession.user_id == User.id)
        .filter(_not_dev)
        .group_by(UserReadingSession.user_id)
        .having(func.count(UserReadingSession.id) >= MIN_READING_SESSIONS)
        .subquery()
    )
    active_classes = (
        session.query(UserCohortMap.cohort_id)
        .join(readers, readers.c.user_id == UserCohortMap.user_id)
        .join(Cohort, Cohort.id == UserCohortMap.cohort_id)
        .filter(func.coalesce(Cohort.is_cohort_of_teachers, False) == False)  # noqa: E712
        .filter(Cohort.is_study == False)  # noqa: E712
        .group_by(UserCohortMap.cohort_id)
        .having(func.count(UserCohortMap.user_id) >= MIN_ACTIVE_STUDENTS)
        .subquery()
    )
    teachers, classes = (
        session.query(
            func.count(distinct(TeacherCohortMap.user_id)),
            func.count(distinct(TeacherCohortMap.cohort_id)),
        )
        .join(active_classes, active_classes.c.cohort_id == TeacherCohortMap.cohort_id)
        .join(User, TeacherCohortMap.user_id == User.id)
        .filter(_not_dev)
        .one()
    )
    return teachers, classes


def compute_platform_totals(session):
    languages = Language.available_languages()
    teachers, classes = _teachers_and_classes(session)
    return {
        "lookups": _lookups(session),
        "exercises": _exercises(session),
        "learners": _learners(session),
        "articles": _articles(session, [l.id for l in languages]),
        "languages": len(languages),
        "teachers": teachers,
        "classes": classes,
    }
