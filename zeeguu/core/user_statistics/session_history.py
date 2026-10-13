"""
A learner's activity as a list of sessions: reading, exercises, browsing and
audio lessons. Shown to the learner on Activity -> History, and to their
teacher for the class's language.

The range is unbounded (a teacher may look at a whole school year), so each
kind of detail is fetched with one query for all sessions, not one per session.
"""

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy.orm import joinedload

from zeeguu.core.constants import (
    EVENT_ARTICLE_FOCUSED,
    EVENT_ARTICLE_LOST_FOCUS,
    EVENT_EXERCISE_LOST_FOCUS,
)
from zeeguu.core.model.article import Article
from zeeguu.core.model.article_summary_context import ArticleSummaryContext
from zeeguu.core.model.article_title_context import ArticleTitleContext
from zeeguu.core.model.url import Url
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_listening_session import UserListeningSession
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_word import UserWord

# What the learner sees is a glimpse of the sentence; the teacher sees it whole.
LEARNER_CONTEXT_LENGTH = 100


def _with_meaning(user_word_relationship):
    meaning = user_word_relationship.joinedload(UserWord.meaning)
    return [
        meaning.joinedload(Meaning.origin),
        meaning.joinedload(Meaning.translation),
    ]


def _practised_user_word_ids(user_word_ids):
    if not user_word_ids:
        return set()
    rows = (
        Exercise.query.with_entities(Exercise.user_word_id)
        .filter(Exercise.user_word_id.in_(user_word_ids))
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def _words_by_session(session_column, session_ids, language_id, for_teacher, with_context):
    """
    {session id: [translated word]} for the bookmarks made in those sessions.
    """
    if not session_ids:
        return {}

    options = _with_meaning(joinedload(Bookmark.user_word))
    if with_context:
        options += [
            joinedload(Bookmark.context).joinedload(BookmarkContext.text),
            joinedload(Bookmark.text),
        ]
    bookmarks = [
        b
        for b in Bookmark.query.options(*options)
        .filter(session_column.in_(session_ids))
        .order_by(Bookmark.time)
        .all()
        if b.user_word.meaning.origin.language_id == language_id
    ]
    practised = (
        _practised_user_word_ids({b.user_word_id for b in bookmarks})
        if for_teacher
        else set()
    )

    result = defaultdict(list)
    for b in bookmarks:
        word = {
            "id": b.id,
            "origin": b.user_word.meaning.origin.content,
            "translation": b.user_word.meaning.translation.content,
        }
        if with_context:
            context = b.get_context() if b.context else None
            if context and not for_teacher:
                context = context[:LEARNER_CONTEXT_LENGTH]
            word["context"] = context
        if for_teacher:
            word["practised"] = b.user_word_id in practised
            # The reader stores an excerpt around the word, not the whole
            # sentence; these say where it was cut, so it can show "…".
            word["context_cut_left"] = bool(b.context and b.context.left_ellipsis)
            word["context_cut_right"] = bool(b.context and b.context.right_ellipsis)
        result[getattr(b, session_column.key)].append(word)
    return result


class _Interruptions:
    """Focus-lost events of one kind, fetched once and counted per session."""

    def __init__(self, user_id, event_type, sessions):
        self.times = []
        if not sessions:
            return
        earliest = min(s.start_time for s in sessions)
        latest = max(_end_time(s) for s in sessions)
        rows = (
            UserActivityData.query.with_entities(UserActivityData.time)
            .filter(UserActivityData.user_id == user_id)
            .filter(UserActivityData.event == event_type)
            .filter(UserActivityData.time >= earliest)
            .filter(UserActivityData.time <= latest)
            .all()
        )
        self.times = sorted(row[0] for row in rows)

    def during(self, session):
        return bisect_right(self.times, _end_time(session)) - bisect_left(
            self.times, session.start_time
        )


class _Away:
    """
    When the article page was not in focus, from its lost-focus and focused
    events: fetched once, cut into intervals per session.
    """

    def __init__(self, user_id, sessions):
        self.events = []
        if not sessions:
            return
        rows = (
            UserActivityData.query.with_entities(
                UserActivityData.time, UserActivityData.event
            )
            .filter(UserActivityData.user_id == user_id)
            .filter(
                UserActivityData.event.in_(
                    [EVENT_ARTICLE_LOST_FOCUS, EVENT_ARTICLE_FOCUSED]
                )
            )
            .filter(UserActivityData.time >= min(s.start_time for s in sessions))
            .filter(UserActivityData.time <= max(_end_time(s) for s in sessions))
            .all()
        )
        self.events = sorted(rows)
        self.times = [time for time, _ in self.events]

    def during(self, session):
        """[[start, end], ...] (UTC ISO) of the session's time away. Away
        from the session start when its first event is coming back (the page
        had not got focus yet); to its end when it never came back."""
        start, end = session.start_time, _end_time(session)
        events = self.events[
            bisect_left(self.times, start) : bisect_right(self.times, end)
        ]
        intervals = []
        left = start if events and events[0][1] == EVENT_ARTICLE_FOCUSED else None
        for time, event in events:
            if event == EVENT_ARTICLE_LOST_FOCUS and left is None:
                left = time
            elif event == EVENT_ARTICLE_FOCUSED and left is not None:
                intervals.append([_utc(left), _utc(time)])
                left = None
        if left is not None and left < end:
            intervals.append([_utc(left), _utc(end)])
        return intervals


def _utc(timestamp):
    """
    Session times are stored as naive UTC (the server's clock). Mark them as
    UTC so the browser shows them in the viewer's own time zone.
    """
    return timestamp.isoformat() + "Z"


def _end_time(session):
    return session.last_action_time if session.last_action_time else session.start_time


def _calculate_focus_level(interruptions, duration_ms):
    """
    Calculate a focus level based on interruptions and duration.

    Returns: 'focused', 'moderate', or 'distracted'
    """
    if duration_ms is None or duration_ms == 0:
        return None

    duration_min = duration_ms / 60000
    interruptions_per_10min = (interruptions / duration_min) * 10 if duration_min > 0 else 0

    if interruptions <= 1 and interruptions_per_10min < 2:
        return "focused"
    elif interruptions <= 3 or interruptions_per_10min < 4:
        return "moderate"
    else:
        return "distracted"


def format_duration(duration_ms):
    """Format duration showing seconds for short durations, minutes for longer ones."""
    if duration_ms is None or duration_ms == 0:
        return "0 sec"
    seconds = duration_ms / 1000
    if seconds < 60:
        return f"{int(seconds)} sec"
    minutes = seconds / 60
    if minutes < 60:
        return f"{round(minutes, 1)} min"
    hours = minutes / 60
    return f"{round(hours, 1)} hr"


def _cefr_level(article):
    """The article's level as the reader shows it: the assessed level when
    there is one, else the level it was crawled with."""
    if article.cefr_assessment and article.cefr_assessment.effective_cefr_level:
        return article.cefr_assessment.effective_cefr_level
    return article.cefr_level


def _reading_completion(user_id, article_ids):
    if not article_ids:
        return {}
    rows = (
        UserArticle.query.with_entities(UserArticle.article_id, UserArticle.reading_completion)
        .filter(UserArticle.user_id == user_id)
        .filter(UserArticle.article_id.in_(article_ids))
        .all()
    )
    return {article_id: value for article_id, value in rows if value is not None}


def _reading_sessions(user_id, language_id, from_date, to_date, for_teacher):
    candidates = (
        UserReadingSession.query.options(
            joinedload(UserReadingSession.article).joinedload(Article.cefr_assessment),
            joinedload(UserReadingSession.article).joinedload(Article.url).joinedload(Url.domain),
        )
        .filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= from_date)
        .filter(UserReadingSession.start_time <= to_date)
        .all()
    )
    reading_sessions = [
        rs
        for rs in candidates
        # no duration: abandoned / never closed; no article: language unknown
        if rs.duration and rs.article and rs.article.language_id == language_id
    ]
    completion = _reading_completion(user_id, {rs.article_id for rs in reading_sessions})
    words = _words_by_session(
        Bookmark.reading_session_id,
        [rs.id for rs in reading_sessions],
        language_id,
        for_teacher,
        with_context=True,
    )
    interruptions = _Interruptions(user_id, EVENT_ARTICLE_LOST_FOCUS, reading_sessions)
    away = _Away(user_id, reading_sessions)

    sessions = []
    for rs in reading_sessions:
        bookmarks = words.get(rs.id, [])
        count = interruptions.during(rs)
        sessions.append(
            {
                "session_type": "reading",
                "start_time": _utc(rs.start_time),
                "end_time": _utc(_end_time(rs)),
                "duration": rs.duration,
                "duration_readable": format_duration(rs.duration),
                "article_id": rs.article_id,
                "article_title": rs.article.title,
                "article_word_count": rs.article.word_count,
                "article_difficulty": rs.article.fk_difficulty,
                "article_cefr_level": _cefr_level(rs.article),
                # the original, at its publisher: what a teacher opens
                "article_url": rs.article.url.as_string() if rs.article.url else None,
                # how far into the text the reader got, 0..1 (latest, not
                # per session: the reader keeps one value per article)
                "reading_completion": completion.get(rs.article_id),
                # 'extension' or 'web'; None for sessions from before the field existed
                "reading_source": rs.reading_source,
                "words": bookmarks,
                "word_count": len(bookmarks),
                "interruptions": count,
                "focus_level": _calculate_focus_level(count, rs.duration),
                # between start_time and end_time, when the page was not in
                # focus: [[start, end], ...]
                "away": away.during(rs),
            }
        )
    return sessions


def _exercises_by_session(session_ids, language_id):
    if not session_ids:
        return {}
    exercises = (
        Exercise.query.options(
            joinedload(Exercise.outcome), *_with_meaning(joinedload(Exercise.user_word))
        )
        .filter(Exercise.session_id.in_(session_ids))
        .order_by(Exercise.time)
        .all()
    )
    result = defaultdict(list)
    for ex in exercises:
        if ex.user_word.meaning.origin.language_id == language_id:
            result[ex.session_id].append(ex)
    return result


def _exercise_sessions(user_id, language_id, from_date, to_date):
    exercise_sessions = UserExerciseSession.find_by_user_id(user_id, from_date, to_date)
    exercises = _exercises_by_session([es.id for es in exercise_sessions], language_id)
    # Only sessions with exercises in this language
    exercise_sessions = [es for es in exercise_sessions if exercises.get(es.id)]
    interruptions = _Interruptions(user_id, EVENT_EXERCISE_LOST_FOCUS, exercise_sessions)

    sessions = []
    for es in exercise_sessions:
        words_practiced = [
            {
                # preferred bookmark, so the learner can edit the word
                "id": ex.user_word.preferred_bookmark_id,
                "origin": ex.user_word.meaning.origin.content,
                "translation": ex.user_word.meaning.translation.content,
                # Same definition as the teacher's "correct on 1st try"
                "correct": ExerciseOutcome.is_correct(ex.outcome.outcome),
            }
            for ex in exercises[es.id]
        ]
        total = len(words_practiced)
        correct = sum(1 for w in words_practiced if w["correct"])
        count = interruptions.during(es)
        sessions.append(
            {
                "session_type": "exercise",
                "start_time": _utc(es.start_time),
                "duration": es.duration,
                "duration_readable": format_duration(es.duration),
                "words": words_practiced,
                "word_count": total,
                "correct_count": correct,
                "accuracy": round(correct / total * 100),
                "interruptions": count,
                "focus_level": _calculate_focus_level(count, es.duration),
            }
        )
    return sessions


def _browsed_articles(bookmark_ids):
    """
    {bookmark id: (article id, title)} for words translated in an article's
    title or summary on the article list.
    """
    result = {}
    if not bookmark_ids:
        return result
    for context in (ArticleTitleContext, ArticleSummaryContext):
        rows = (
            context.query.join(Article, Article.id == context.article_id)
            .filter(context.bookmark_id.in_(bookmark_ids))
            .with_entities(context.bookmark_id, Article.id, Article.title)
            .all()
        )
        for bookmark_id, article_id, title in rows:
            result.setdefault(bookmark_id, (article_id, title))
    return result


def _browsing_sessions(user_id, language_id, from_date, to_date, for_teacher):
    browsing_sessions = [
        bs
        for bs in UserBrowsingSession.find_by_user(user_id, from_date, to_date)
        # language_id is the learned language when the session started
        if bs.duration and bs.language_id in (None, language_id)
    ]
    words = _words_by_session(
        Bookmark.browsing_session_id,
        [bs.id for bs in browsing_sessions],
        language_id,
        for_teacher,
        with_context=for_teacher,
    )
    # Which article each word was translated in, so the words of a browsing
    # session can be shown under the title they came from.
    all_words = [w for ws in words.values() for w in ws]
    articles = _browsed_articles([w["id"] for w in all_words])
    for word in all_words:
        word["article_id"], word["article_title"] = articles.get(
            word["id"], (None, None)
        )

    sessions = []
    for bs in browsing_sessions:
        bookmarks = words.get(bs.id, [])
        # Browsing without translating (previews, search) still counts: a
        # student who browsed but never opened an article must not look idle.
        # Older sessions have no language; their translations are all we have
        # to go on.
        if bs.language_id is None and not bookmarks:
            continue
        sessions.append(
            {
                "session_type": "browsing",
                "start_time": _utc(bs.start_time),
                "end_time": _utc(_end_time(bs)),
                "duration": bs.duration,
                "duration_readable": format_duration(bs.duration),
                "words": bookmarks,
                "word_count": len(bookmarks),
            }
        )
    return sessions


def _words_for_audio_lesson(audio_lesson, language_id):
    """Get all words/meanings included in an audio lesson."""
    result = []
    for segment in audio_lesson.segments:
        if segment.segment_type == "meaning_lesson" and segment.audio_lesson_meaning:
            meaning = segment.audio_lesson_meaning.meaning
            if meaning.origin.language_id != language_id:
                continue
            result.append({
                "origin": meaning.origin.content,
                "translation": meaning.translation.content,
            })
    return result


def _audio_sessions(user_id, language_id, from_date, to_date):
    # At most one lesson a day, so the per-lesson word lookup stays small.
    sessions = []
    listening_sessions = UserListeningSession.find_by_user_and_language(
        user_id, language_id, from_date, to_date
    )
    for ls in listening_sessions:
        if not ls.duration:
            continue
        audio_lesson = ls.daily_audio_lesson
        is_completed = audio_lesson.is_completed if audio_lesson else False

        # Only show words for completed lessons (incomplete = unknown coverage)
        words = _words_for_audio_lesson(audio_lesson, language_id) if is_completed else []

        sessions.append(
            {
                "session_type": "audio",
                "start_time": _utc(ls.start_time),
                "duration": ls.duration,  # Already in milliseconds
                "duration_readable": format_duration(ls.duration),
                "words": words,
                "word_count": len(words),
                "completed": is_completed,
                "lesson_id": audio_lesson.id if audio_lesson else None,
                "lesson_title": audio_lesson.display_title() if audio_lesson else None,
            }
        )
    return sessions


def session_history(user_id, language_id, from_date, to_date, for_teacher=False):
    """
    All sessions in [from_date, to_date] in the given language, newest first.

    for_teacher: translated words carry their full sentence and whether the
    student practised them since; browsing sessions list their words with
    context too.
    """
    sessions = (
        _reading_sessions(user_id, language_id, from_date, to_date, for_teacher)
        + _exercise_sessions(user_id, language_id, from_date, to_date)
        + _browsing_sessions(user_id, language_id, from_date, to_date, for_teacher)
        + _audio_sessions(user_id, language_id, from_date, to_date)
    )
    sessions.sort(key=lambda s: s["start_time"])
    return list(reversed(_merge_consecutive_browsing(sessions)))


# Browsing sessions closer together than this are one visit to the app
BROWSING_MERGE_GAP = timedelta(minutes=30)


def _continues(previous, session):
    """session picks up where previous left off: browsing after browsing, or
    the same article read again, starting within BROWSING_MERGE_GAP."""
    if not previous or previous["session_type"] != session["session_type"]:
        return False
    if session["session_type"] == "reading":
        if previous.get("article_id") != session.get("article_id"):
            return False
    elif session["session_type"] != "browsing":
        return False
    gap = datetime.fromisoformat(session["start_time"]) - datetime.fromisoformat(previous["end_time"])
    return gap <= BROWSING_MERGE_GAP


def _merge_consecutive_browsing(sessions):
    """
    Every visit to the article list is its own browsing session, and leaving
    an article and coming back starts a new reading session, so one sitting
    leaves several short ones. Browsing sessions with nothing else in between,
    and readings of the same article with nothing else in between, each
    starting within BROWSING_MERGE_GAP of the previous one's last action,
    become one entry. Durations add up, so totals computed from the list stay
    exact.

    sessions: in chronological order.
    """
    merged = []
    for session in sessions:
        previous = merged[-1] if merged else None
        if _continues(previous, session):
            previous_end = previous["end_time"]
            previous["end_time"] = max(previous["end_time"], session["end_time"])
            previous["duration"] += session["duration"]
            previous["duration_readable"] = format_duration(previous["duration"])
            previous["words"] += session["words"]
            previous["word_count"] = len(previous["words"])
            previous["merged_sessions"] += 1
            if session["session_type"] == "reading":
                # the article closed between the two counts as away
                previous["away"] += [[previous_end, session["start_time"]]] + session["away"]
                previous["interruptions"] += session["interruptions"]
                previous["focus_level"] = _calculate_focus_level(
                    previous["interruptions"], previous["duration"]
                )
            continue
        if session["session_type"] in ("browsing", "reading"):
            session["merged_sessions"] = 1
        merged.append(session)
    return merged
