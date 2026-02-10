"""
User activity statistics endpoint for monitoring daily user engagement.
Shows exercise sessions, reading sessions, and word progress grouped by language.
Replaces frequent email notifications with a consolidated dashboard view.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from flask import request, Response, make_response, redirect

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session, only_admins
from zeeguu.core.model import User, Language, Session
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.user_browsing_session import UserBrowsingSession
from zeeguu.core.model.user_cohort_map import UserCohortMap
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.constants import PLATFORM_NAMES
from . import api, db_session


def get_period_range(period: str):
    """Get start and end datetime for the given period."""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        start = today_start
        end = now
        label = "Today"
    elif period == "week":
        start = today_start - timedelta(days=7)
        end = today_start
        label = "Last 7 days"
    elif period == "month":
        start = today_start - timedelta(days=30)
        end = today_start
        label = "Last 30 days"
    elif period == "2days":
        start = today_start - timedelta(days=2)
        end = today_start - timedelta(days=1)
        label = "Two days ago"
    else:  # yesterday (default)
        start = today_start - timedelta(days=1)
        end = today_start
        label = "Yesterday"

    return start, end, label


def get_platform_stats(start, end):
    """Get platform usage statistics from user_activity_data for the given period."""
    from sqlalchemy import func

    # Query activity counts grouped by platform
    platform_counts = (
        db_session.query(
            UserActivityData.platform,
            func.count(func.distinct(UserActivityData.user_id)).label('user_count'),
            func.count(UserActivityData.id).label('event_count')
        )
        .filter(UserActivityData.time >= start)
        .filter(UserActivityData.time < end)
        .group_by(UserActivityData.platform)
        .all()
    )

    # Get distinct user IDs for each platform
    platform_users = {}
    for platform_id, _, _ in platform_counts:
        user_ids = (
            db_session.query(func.distinct(UserActivityData.user_id))
            .filter(UserActivityData.time >= start)
            .filter(UserActivityData.time < end)
            .filter(UserActivityData.platform == platform_id)
            .all()
        )
        platform_users[platform_id] = [uid[0] for uid in user_ids]

    stats = {}
    for platform_id, user_count, event_count in platform_counts:
        platform_name = PLATFORM_NAMES.get(platform_id, f"unknown ({platform_id})")
        stats[platform_name] = {
            'users': user_count,
            'events': event_count,
            'platform_id': platform_id,
            'user_ids': platform_users.get(platform_id, [])
        }

    return stats


def get_user_cohort_info(user):
    """Get cohort name or invite code for a user."""
    # First check UserCohortMap
    cohort_map = UserCohortMap.query.filter_by(user_id=user.id).first()
    if cohort_map and cohort_map.cohort:
        return cohort_map.cohort.name, cohort_map.cohort.id

    # Fall back to invite code
    if user.invitation_code:
        # Check if this invite code belongs to a cohort
        cohort = Cohort.query.filter_by(inv_code=user.invitation_code).first()
        if cohort:
            return cohort.name, cohort.id
        return user.invitation_code, None

    return None, None


def get_exercise_stats_for_user(user_id, start, end):
    """Get exercise session stats for a user in the given period."""
    sessions = (
        UserExerciseSession.query.filter(UserExerciseSession.user_id == user_id)
        .filter(UserExerciseSession.start_time >= start)
        .filter(UserExerciseSession.start_time < end)
        .all()
    )

    total_duration_ms = sum(s.duration or 0 for s in sessions)
    session_count = len(sessions)

    # Get unique words practiced and language info
    words_by_language = defaultdict(set)

    for session in sessions:
        exercises = Exercise.query.filter(Exercise.session_id == session.id).all()
        for ex in exercises:
            if ex.user_word and ex.user_word.meaning and ex.user_word.meaning.origin:
                lang = ex.user_word.meaning.origin.language
                if lang:
                    words_by_language[lang.code].add(ex.user_word_id)

    return {
        "session_count": session_count,
        "duration_ms": total_duration_ms,
        "duration_min": round(total_duration_ms / 60000, 1),
        "words_by_language": {
            lang: len(words) for lang, words in words_by_language.items()
        },
        "sessions": sessions,
    }


def get_reading_stats_for_user(user_id, start, end):
    """Get reading session stats for a user in the given period."""
    sessions = (
        UserReadingSession.query.filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= start)
        .filter(UserReadingSession.start_time < end)
        .all()
    )

    total_duration_ms = sum(s.duration or 0 for s in sessions)

    # Group by article and language
    articles_by_language = defaultdict(set)

    for session in sessions:
        if session.article and session.article.language:
            lang_code = session.article.language.code
            articles_by_language[lang_code].add(session.article_id)

    return {
        "session_count": len(sessions),
        "duration_ms": total_duration_ms,
        "duration_min": round(total_duration_ms / 60000, 1),
        "articles_by_language": {
            lang: len(arts) for lang, arts in articles_by_language.items()
        },
        "sessions": sessions,
    }


def get_browsing_stats_for_user(user_id, start, end):
    """Get browsing session stats for a user in the given period."""
    sessions = (
        UserBrowsingSession.query.filter(UserBrowsingSession.user_id == user_id)
        .filter(UserBrowsingSession.start_time >= start)
        .filter(UserBrowsingSession.start_time < end)
        .all()
    )

    total_duration_ms = sum(s.duration or 0 for s in sessions)

    # Get translations made during browsing sessions
    words_by_language = defaultdict(int)
    session_ids = [s.id for s in sessions]

    if session_ids:
        browsing_bookmarks = (
            Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user_id)
            .filter(Bookmark.browsing_session_id.in_(session_ids))
            .all()
        )
        for bm in browsing_bookmarks:
            if bm.user_word and bm.user_word.meaning and bm.user_word.meaning.origin:
                lang = bm.user_word.meaning.origin.language
                if lang:
                    words_by_language[lang.code] += 1

    return {
        "session_count": len(sessions),
        "duration_ms": total_duration_ms,
        "duration_min": round(total_duration_ms / 60000, 1),
        "words_by_language": dict(words_by_language),
        "sessions": sessions,
    }


def get_translations_for_user(user_id, start, end):
    """Get translations/bookmarks made by user in the given period."""
    from zeeguu.core.model.bookmark import Bookmark

    bookmarks = (
        Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
        .filter(UserWord.user_id == user_id)
        .filter(Bookmark.time >= start)
        .filter(Bookmark.time < end)
        .all()
    )

    translations_by_language = defaultdict(int)
    for bm in bookmarks:
        if bm.user_word and bm.user_word.meaning and bm.user_word.meaning.origin:
            lang = bm.user_word.meaning.origin.language
            if lang:
                translations_by_language[lang.code] += 1

    return {
        "total": len(bookmarks),
        "by_language": dict(translations_by_language),
    }


def get_audio_lesson_stats_for_user(user_id, start, end):
    """Get audio lesson stats for a user in the given period."""
    # Get lessons completed in this period
    lessons = (
        DailyAudioLesson.query.filter(DailyAudioLesson.user_id == user_id)
        .filter(DailyAudioLesson.completed_at >= start)
        .filter(DailyAudioLesson.completed_at < end)
        .all()
    )

    total_duration_sec = sum(l.duration_seconds or 0 for l in lessons)

    # Group by language
    lessons_by_language = defaultdict(int)
    duration_by_language = defaultdict(int)

    for lesson in lessons:
        if lesson.language:
            lang_code = lesson.language.code
            lessons_by_language[lang_code] += 1
            duration_by_language[lang_code] += lesson.duration_seconds or 0

    return {
        "lesson_count": len(lessons),
        "duration_sec": total_duration_sec,
        "duration_min": round(total_duration_sec / 60, 1),
        "lessons_by_language": dict(lessons_by_language),
        "duration_by_language": {
            lang: round(sec / 60, 1) for lang, sec in duration_by_language.items()
        },
        "lessons": lessons,
    }


def collect_user_activity(start, end):
    """Collect activity stats for all users in the given period."""

    # Find all users with exercise sessions in this period
    exercise_user_ids = (
        db_session.query(UserExerciseSession.user_id)
        .filter(UserExerciseSession.start_time >= start)
        .filter(UserExerciseSession.start_time < end)
        .distinct()
        .all()
    )

    # Find all users with reading sessions in this period
    reading_user_ids = (
        db_session.query(UserReadingSession.user_id)
        .filter(UserReadingSession.start_time >= start)
        .filter(UserReadingSession.start_time < end)
        .distinct()
        .all()
    )

    # Find all users with translations/bookmarks in this period
    bookmark_user_ids = (
        db_session.query(UserWord.user_id)
        .join(Bookmark, Bookmark.user_word_id == UserWord.id)
        .filter(Bookmark.time >= start)
        .filter(Bookmark.time < end)
        .distinct()
        .all()
    )

    # Find all users with completed audio lessons in this period
    audio_lesson_user_ids = (
        db_session.query(DailyAudioLesson.user_id)
        .filter(DailyAudioLesson.completed_at >= start)
        .filter(DailyAudioLesson.completed_at < end)
        .distinct()
        .all()
    )

    # Find all users with browsing sessions in this period
    browsing_user_ids = (
        db_session.query(UserBrowsingSession.user_id)
        .filter(UserBrowsingSession.start_time >= start)
        .filter(UserBrowsingSession.start_time < end)
        .distinct()
        .all()
    )

    # Combine unique user IDs from all activity types
    active_user_ids = (
        set(uid for (uid,) in exercise_user_ids)
        | set(uid for (uid,) in reading_user_ids)
        | set(uid for (uid,) in bookmark_user_ids)
        | set(uid for (uid,) in audio_lesson_user_ids)
        | set(uid for (uid,) in browsing_user_ids)
    )

    # Collect stats per user, grouped by language
    users_by_language = defaultdict(list)

    for user_id in active_user_ids:
        user = User.find_by_id(user_id)
        if not user:
            continue

        cohort_name, cohort_id = get_user_cohort_info(user)
        exercise_stats = get_exercise_stats_for_user(user_id, start, end)
        reading_stats = get_reading_stats_for_user(user_id, start, end)
        browsing_stats = get_browsing_stats_for_user(user_id, start, end)
        translation_stats = get_translations_for_user(user_id, start, end)
        audio_stats = get_audio_lesson_stats_for_user(user_id, start, end)

        # Determine languages from activity
        active_languages = set()
        active_languages.update(exercise_stats["words_by_language"].keys())
        active_languages.update(reading_stats["articles_by_language"].keys())
        active_languages.update(browsing_stats["words_by_language"].keys())
        active_languages.update(translation_stats["by_language"].keys())
        active_languages.update(audio_stats["lessons_by_language"].keys())

        if not active_languages:
            active_languages = {"unknown"}

        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "cohort_name": cohort_name,
            "cohort_id": cohort_id,
            "exercise_duration_min": exercise_stats["duration_min"],
            "exercise_sessions": exercise_stats["session_count"],
            "exercise_words": exercise_stats["words_by_language"],
            "reading_duration_min": reading_stats["duration_min"],
            "articles_read": reading_stats["articles_by_language"],
            "browsing_duration_min": browsing_stats["duration_min"],
            "browsing_words": browsing_stats["words_by_language"],
            "translations": translation_stats["by_language"],
            "audio_lessons": audio_stats["lessons_by_language"],
            "audio_duration_min": audio_stats["duration_min"],
            "audio_duration_by_language": audio_stats["duration_by_language"],
            "languages": list(active_languages),
        }

        # Add user to each language they were active in
        for lang in active_languages:
            users_by_language[lang].append(user_data)

    return users_by_language


@api.route("/user_stats", methods=["GET"])
@cross_domain
@requires_session
@only_admins
def user_stats():
    """
    Get user activity statistics for yesterday or last week.

    Query params:
        period: "yesterday" (default) or "week"

    Returns JSON with users grouped by activity language.
    """
    period = request.args.get("period", "yesterday")
    start, end, period_label = get_period_range(period)

    users_by_language = collect_user_activity(start, end)

    # Calculate totals per language
    result = {
        "period": {
            "name": period,
            "label": period_label,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "by_language": {},
        "summary": {
            "total_active_users": 0,
            "total_exercise_minutes": 0,
            "total_reading_minutes": 0,
        },
    }

    seen_users = set()

    for lang_code, users in users_by_language.items():
        lang_exercise_min = sum(u["exercise_duration_min"] for u in users)
        lang_reading_min = sum(u["reading_duration_min"] for u in users)

        result["by_language"][lang_code] = {
            "user_count": len(users),
            "exercise_minutes": round(lang_exercise_min, 1),
            "reading_minutes": round(lang_reading_min, 1),
            "users": sorted(
                users, key=lambda u: u["exercise_duration_min"], reverse=True
            ),
        }

        result["summary"]["total_exercise_minutes"] += lang_exercise_min
        result["summary"]["total_reading_minutes"] += lang_reading_min

        for u in users:
            seen_users.add(u["id"])

    result["summary"]["total_active_users"] = len(seen_users)
    result["summary"]["total_exercise_minutes"] = round(
        result["summary"]["total_exercise_minutes"], 1
    )
    result["summary"]["total_reading_minutes"] = round(
        result["summary"]["total_reading_minutes"], 1
    )

    return result


@api.route("/user_stats/user/<int:user_id>", methods=["GET"])
@cross_domain
@requires_session
@only_admins
def user_stats_individual(user_id):
    """
    Get detailed activity statistics for a specific user.

    Query params:
        period: "yesterday" (default) or "week"
    """
    period = request.args.get("period", "yesterday")
    start, end, period_label = get_period_range(period)

    user = User.find_by_id(user_id)
    if not user:
        return {"error": "User not found"}, 404

    cohort_name, cohort_id = get_user_cohort_info(user)

    # Get exercise sessions with details
    exercise_sessions = (
        UserExerciseSession.query.filter(UserExerciseSession.user_id == user_id)
        .filter(UserExerciseSession.start_time >= start)
        .filter(UserExerciseSession.start_time < end)
        .order_by(UserExerciseSession.start_time.desc())
        .all()
    )

    exercise_session_details = []
    for session in exercise_sessions:
        exercises = Exercise.query.filter(Exercise.session_id == session.id).all()

        words = []
        session_lang = None
        for ex in exercises:
            if ex.user_word and ex.user_word.meaning:
                origin = ex.user_word.meaning.origin
                translation = ex.user_word.meaning.translation
                if origin:
                    if origin.language and not session_lang:
                        session_lang = origin.language.code
                    words.append(
                        {
                            "word": origin.content if origin else "?",
                            "translation": translation.content if translation else "?",
                            "outcome": ex.outcome.outcome if ex.outcome else "?",
                            "solving_speed_ms": ex.solving_speed,
                        }
                    )

        exercise_session_details.append(
            {
                "id": session.id,
                "start_time": session.start_time.isoformat(),
                "duration_min": round((session.duration or 0) / 60000, 1),
                "language": session_lang,
                "word_count": len(words),
                "words": words,
            }
        )

    # Get reading sessions with details
    reading_sessions = (
        UserReadingSession.query.filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= start)
        .filter(UserReadingSession.start_time < end)
        .order_by(UserReadingSession.start_time.desc())
        .all()
    )

    reading_session_details = []
    for session in reading_sessions:
        article = session.article
        reading_session_details.append(
            {
                "id": session.id,
                "start_time": session.start_time.isoformat(),
                "duration_min": round((session.duration or 0) / 60000, 1),
                "article_id": session.article_id,
                "article_title": article.title if article else "Unknown",
                "article_language": (
                    article.language.code if article and article.language else None
                ),
            }
        )

    # Get translations/bookmarks
    bookmarks = (
        Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
        .filter(UserWord.user_id == user_id)
        .filter(Bookmark.time >= start)
        .filter(Bookmark.time < end)
        .order_by(Bookmark.time.desc())
        .all()
    )

    translation_details = []
    for bm in bookmarks:
        if bm.user_word and bm.user_word.meaning:
            origin = bm.user_word.meaning.origin
            translation = bm.user_word.meaning.translation
            translation_details.append(
                {
                    "word": origin.content if origin else "?",
                    "translation": translation.content if translation else "?",
                    "time": bm.time.isoformat() if bm.time else None,
                    "language": (
                        origin.language.code if origin and origin.language else None
                    ),
                }
            )

    return {
        "period": {
            "name": period,
            "label": period_label,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "cohort_name": cohort_name,
            "cohort_id": cohort_id,
        },
        "exercise_sessions": exercise_session_details,
        "reading_sessions": reading_session_details,
        "translations": translation_details,
        "summary": {
            "exercise_session_count": len(exercise_session_details),
            "exercise_minutes": round(
                sum(s["duration_min"] for s in exercise_session_details), 1
            ),
            "reading_session_count": len(reading_session_details),
            "reading_minutes": round(
                sum(s["duration_min"] for s in reading_session_details), 1
            ),
            "translation_count": len(translation_details),
        },
    }


@api.route("/user_stats/dashboard", methods=["GET"])
@cross_domain
@requires_session
@only_admins
def user_stats_dashboard():
    """HTML dashboard showing user activity statistics."""
    period = request.args.get("period", "yesterday")
    start, end, period_label = get_period_range(period)

    users_by_language = collect_user_activity(start, end)
    platform_stats = get_platform_stats(start, end)

    # Calculate totals
    total_users = set()
    total_exercise_min = 0
    total_reading_min = 0
    total_browsing_min = 0
    total_audio_min = 0

    for lang_code, users in users_by_language.items():
        for u in users:
            total_users.add(u["id"])
            total_exercise_min += u["exercise_duration_min"]
            total_reading_min += u["reading_duration_min"]
            total_browsing_min += u["browsing_duration_min"]
            total_audio_min += u["audio_duration_by_language"].get(lang_code, 0)

    # Get language names
    languages = {l.code: l.name for l in Language.available_languages()}

    # Sort languages by activity
    sorted_languages = sorted(
        users_by_language.items(),
        key=lambda x: sum(
            u["exercise_duration_min"] + u["reading_duration_min"] for u in x[1]
        ),
        reverse=True,
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Zeeguu User Stats</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #2c3e50; margin-bottom: 5px; }}
        .subtitle {{ color: #7f8c8d; margin-bottom: 20px; }}
        .summary {{
            display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap;
        }}
        .stat-card {{
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 150px;
        }}
        .stat-card .number {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .stat-card .label {{ color: #7f8c8d; font-size: 0.9em; }}
        .section {{
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{ margin-top: 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .section h3 {{ margin-top: 20px; color: #34495e; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        th.group-header {{
            text-align: center;
            background: #e8f4f8;
            border-bottom: 2px solid #3498db;
            font-size: 0.95em;
        }}
        th.sub-header {{
            font-size: 0.85em;
            color: #666;
            font-weight: 500;
        }}
        tr:hover {{ background: #f8f9fa; }}
        .lang-code {{
            display: inline-block; padding: 2px 8px;
            background: #3498db; color: white; border-radius: 4px;
            font-weight: bold; font-size: 0.9em;
        }}
        .cohort-badge {{
            display: inline-block; padding: 2px 6px;
            background: #ecf0f1; color: #7f8c8d; border-radius: 4px;
            font-size: 0.85em;
        }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block; padding: 8px 16px; margin-right: 10px;
            background: #3498db; color: white; text-decoration: none;
            border-radius: 4px;
        }}
        .nav a:hover {{ background: #2980b9; }}
        .nav a.active {{ background: #2c3e50; }}
        .user-link {{ color: #3498db; text-decoration: none; }}
        .user-link:hover {{ text-decoration: underline; }}
        .cohort-link {{
            display: inline-block; padding: 2px 6px;
            background: #3498db; color: white; border-radius: 4px;
            font-size: 0.85em; text-decoration: none;
        }}
        .cohort-link:hover {{ background: #2980b9; }}
        .no-activity {{ color: #bdc3c7; }}
        .duration {{ font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>User Activity Stats</h1>
        <p class="subtitle">
            {period_label} ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})
        </p>

        <div class="nav">
            <a href="?period=today" {"class='active'" if period == "today" else ""}>Today</a>
            <a href="?period=yesterday" {"class='active'" if period == "yesterday" else ""}>Yesterday</a>
            <a href="?period=2days" {"class='active'" if period == "2days" else ""}>2 days ago</a>
            <a href="?period=week" {"class='active'" if period == "week" else ""}>Last 7 days</a>
            <a href="?period=month" {"class='active'" if period == "month" else ""}>Last 30 days</a>
        </div>

        <div class="summary">
            <div class="stat-card">
                <div class="number">{len(total_users)}</div>
                <div class="label">Active Users</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_exercise_min, 0):.0f}</div>
                <div class="label">Exercise Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_reading_min, 0):.0f}</div>
                <div class="label">Reading Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_browsing_min, 0):.0f}</div>
                <div class="label">Browsing Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_audio_min, 0):.0f}</div>
                <div class="label">Audio Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(users_by_language)}</div>
                <div class="label">Languages</div>
            </div>
        </div>

        <div class="section">
            <h2>Platform Usage</h2>
            <table>
                <tr>
                    <th>Platform</th>
                    <th>Active Users</th>
                    <th>Events</th>
                </tr>
"""

    # Sort platforms by user count
    sorted_platforms = sorted(platform_stats.items(), key=lambda x: x[1]['users'], reverse=True)
    for platform_name, stats in sorted_platforms:
        platform_id = stats['platform_id']
        user_link = f'<a href="/user_stats/platform/{platform_id}/dashboard?period={period}">{stats["users"]}</a>'
        html += f"""
                <tr>
                    <td>{platform_name}</td>
                    <td>{user_link}</td>
                    <td>{stats['events']}</td>
                </tr>
"""

    if not platform_stats:
        html += """
                <tr>
                    <td colspan="3" style="text-align:center; color:#7f8c8d;">No platform data available</td>
                </tr>
"""

    html += """
            </table>
        </div>
"""

    for lang_code, users in sorted_languages:
        lang_name = languages.get(lang_code, lang_code.upper())
        lang_exercise_min = sum(u["exercise_duration_min"] for u in users)
        lang_reading_min = sum(u["reading_duration_min"] for u in users)
        lang_browsing_min = sum(u["browsing_duration_min"] for u in users)

        # Sort users by total activity
        sorted_users = sorted(
            users,
            key=lambda u: u["exercise_duration_min"]
            + u["reading_duration_min"]
            + u["browsing_duration_min"],
            reverse=True,
        )

        html += f"""
        <div class="section">
            <h2><span class="lang-code">{lang_code.upper()}</span> {lang_name}</h2>
            <p style="color:#7f8c8d; margin-bottom:15px;">
                {len(users)} active users |
                {round(lang_exercise_min, 0):.0f} min exercises |
                {round(lang_reading_min, 0):.0f} min reading |
                {round(lang_browsing_min, 0):.0f} min browsing
            </p>
            <table>
                <tr>
                    <th rowspan="2">User</th>
                    <th rowspan="2">Cohort / Code</th>
                    <th colspan="2" class="group-header">Exercises</th>
                    <th colspan="2" class="group-header">Reading</th>
                    <th colspan="2" class="group-header">Browsing</th>
                    <th colspan="2" class="group-header">Audio</th>
                </tr>
                <tr>
                    <th class="sub-header">Time</th>
                    <th class="sub-header">Words</th>
                    <th class="sub-header">Time</th>
                    <th class="sub-header">Articles</th>
                    <th class="sub-header">Time</th>
                    <th class="sub-header">Words</th>
                    <th class="sub-header">Count</th>
                    <th class="sub-header">Time</th>
                </tr>
"""

        for user in sorted_users:
            cohort_display = user["cohort_name"] or "—"
            exercise_words = user["exercise_words"].get(lang_code, 0)
            articles = user["articles_read"].get(lang_code, 0)
            browsing_words = user["browsing_words"].get(lang_code, 0)

            exercise_class = "" if user["exercise_duration_min"] > 0 else "no-activity"
            reading_class = "" if user["reading_duration_min"] > 0 else "no-activity"
            browsing_class = "" if user["browsing_duration_min"] > 0 else "no-activity"

            audio_lessons = user["audio_lessons"].get(lang_code, 0)
            audio_duration = user["audio_duration_by_language"].get(lang_code, 0)
            audio_class = "" if audio_lessons > 0 else "no-activity"

            # Make cohort clickable if it has an ID
            if user["cohort_id"]:
                cohort_html = f'<a href="/user_stats/cohort/{user["cohort_id"]}/dashboard?period={period}" class="cohort-link">{cohort_display}</a>'
            else:
                cohort_html = f'<span class="cohort-badge">{cohort_display}</span>'

            html += f"""
                <tr>
                    <td><a href="/user_stats/user/{user['id']}/dashboard?period={period}" class="user-link">{user['name']}</a></td>
                    <td>{cohort_html}</td>
                    <td class="{exercise_class} duration">{user['exercise_duration_min']:.1f} min</td>
                    <td class="{exercise_class}">{exercise_words}</td>
                    <td class="{reading_class} duration">{user['reading_duration_min']:.1f} min</td>
                    <td class="{reading_class}">{articles}</td>
                    <td class="{browsing_class} duration">{user['browsing_duration_min']:.1f} min</td>
                    <td class="{browsing_class}">{browsing_words}</td>
                    <td class="{audio_class}">{audio_lessons}</td>
                    <td class="{audio_class} duration">{audio_duration:.1f} min</td>
                </tr>
"""

        html += """
            </table>
        </div>
"""

    if not users_by_language:
        html += """
        <div class="section">
            <p style="text-align:center; color:#7f8c8d; padding: 40px;">
                No user activity in this period.
            </p>
        </div>
"""

    html += f"""
        <p style="color:#7f8c8d; font-size:0.9em; margin-top:30px;">
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
            <a href="/user_stats?period={period}">JSON API</a>
        </p>
    </div>
</body>
</html>"""

    return Response(html, mimetype="text/html")


@api.route("/user_stats/user/<int:user_id>/dashboard", methods=["GET"])
@cross_domain
@requires_session
@only_admins
def user_stats_individual_dashboard(user_id):
    """HTML dashboard for individual user activity."""
    period = request.args.get("period", "yesterday")
    start, end, period_label = get_period_range(period)

    user = User.find_by_id(user_id)
    if not user:
        return Response("<h1>User not found</h1>", status=404, mimetype="text/html")

    cohort_name, cohort_id = get_user_cohort_info(user)

    # Get exercise sessions with details
    exercise_sessions = (
        UserExerciseSession.query.filter(UserExerciseSession.user_id == user_id)
        .filter(UserExerciseSession.start_time >= start)
        .filter(UserExerciseSession.start_time < end)
        .order_by(UserExerciseSession.start_time.desc())
        .all()
    )

    # Get reading sessions with details
    reading_sessions = (
        UserReadingSession.query.filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= start)
        .filter(UserReadingSession.start_time < end)
        .order_by(UserReadingSession.start_time.desc())
        .all()
    )

    # Get translations/bookmarks
    bookmarks = (
        Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
        .filter(UserWord.user_id == user_id)
        .filter(Bookmark.time >= start)
        .filter(Bookmark.time < end)
        .order_by(Bookmark.time.desc())
        .all()
    )

    # Get audio lessons
    audio_lessons = (
        DailyAudioLesson.query.filter(DailyAudioLesson.user_id == user_id)
        .filter(DailyAudioLesson.completed_at >= start)
        .filter(DailyAudioLesson.completed_at < end)
        .order_by(DailyAudioLesson.completed_at.desc())
        .all()
    )

    # Calculate totals
    total_exercise_min = sum((s.duration or 0) / 60000 for s in exercise_sessions)
    total_reading_min = sum((s.duration or 0) / 60000 for s in reading_sessions)
    total_audio_min = sum((l.duration_seconds or 0) / 60 for l in audio_lessons)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{user.name} - User Stats</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #2c3e50; margin-bottom: 5px; }}
        .subtitle {{ color: #7f8c8d; margin-bottom: 20px; }}
        .back-link {{ color: #3498db; text-decoration: none; margin-bottom: 15px; display: inline-block; }}
        .back-link:hover {{ text-decoration: underline; }}
        .summary {{
            display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap;
        }}
        .stat-card {{
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 150px;
        }}
        .stat-card .number {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .stat-card .label {{ color: #7f8c8d; font-size: 0.9em; }}
        .section {{
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{ margin-top: 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .session-card {{
            background: #f8f9fa; padding: 15px; border-radius: 6px;
            margin-bottom: 15px; border-left: 4px solid #3498db;
        }}
        .session-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 10px;
        }}
        .session-time {{ font-weight: bold; color: #2c3e50; }}
        .session-duration {{ color: #7f8c8d; font-family: monospace; }}
        .session-lang {{
            background: #3498db; color: white; padding: 2px 6px;
            border-radius: 4px; font-size: 0.8em;
        }}
        .word-list {{ margin: 0; padding-left: 20px; }}
        .word-list li {{ margin: 3px 0; font-size: 0.95em; }}
        .word-correct {{ color: #27ae60; }}
        .word-incorrect {{ color: #e74c3c; }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block; padding: 8px 16px; margin-right: 10px;
            background: #3498db; color: white; text-decoration: none;
            border-radius: 4px;
        }}
        .nav a:hover {{ background: #2980b9; }}
        .nav a.active {{ background: #2c3e50; }}
        .cohort-badge {{
            background: #ecf0f1; color: #7f8c8d; padding: 4px 8px;
            border-radius: 4px; font-size: 0.9em;
        }}
        .article-link {{ color: #3498db; text-decoration: none; }}
        .article-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/user_stats/dashboard?period={period}" class="back-link">&larr; Back to overview</a>
        <h1>{user.name}</h1>
        <p class="subtitle">
            {user.email} |
            <span class="cohort-badge">{cohort_name or "No cohort"}</span> |
            {period_label}
        </p>

        <div class="nav">
            <a href="?period=today" {"class='active'" if period == "today" else ""}>Today</a>
            <a href="?period=yesterday" {"class='active'" if period == "yesterday" else ""}>Yesterday</a>
            <a href="?period=2days" {"class='active'" if period == "2days" else ""}>2 days ago</a>
            <a href="?period=week" {"class='active'" if period == "week" else ""}>Last 7 days</a>
            <a href="?period=month" {"class='active'" if period == "month" else ""}>Last 30 days</a>
        </div>

        <div class="summary">
            <div class="stat-card">
                <div class="number">{len(exercise_sessions)}</div>
                <div class="label">Exercise Sessions</div>
            </div>
            <div class="stat-card">
                <div class="number">{total_exercise_min:.0f}</div>
                <div class="label">Exercise Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(reading_sessions)}</div>
                <div class="label">Reading Sessions</div>
            </div>
            <div class="stat-card">
                <div class="number">{total_reading_min:.0f}</div>
                <div class="label">Reading Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(audio_lessons)}</div>
                <div class="label">Audio Lessons</div>
            </div>
            <div class="stat-card">
                <div class="number">{total_audio_min:.0f}</div>
                <div class="label">Audio Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(bookmarks)}</div>
                <div class="label">Translations</div>
            </div>
        </div>

        <div class="section">
            <h2>Exercise Sessions</h2>
"""

    if exercise_sessions:
        for session in exercise_sessions:
            exercises = Exercise.query.filter(Exercise.session_id == session.id).all()
            duration_min = (session.duration or 0) / 60000

            # Determine language from exercises
            session_lang = None
            words_html = ""
            for ex in exercises:
                if ex.user_word and ex.user_word.meaning:
                    origin = ex.user_word.meaning.origin
                    translation = ex.user_word.meaning.translation
                    if origin and origin.language and not session_lang:
                        session_lang = origin.language.code.upper()

                    outcome = ex.outcome.outcome if ex.outcome else "?"
                    outcome_class = (
                        "word-correct"
                        if outcome == "C"
                        else "word-incorrect" if outcome == "W" else ""
                    )
                    word = origin.content if origin else "?"
                    trans = translation.content if translation else "?"
                    speed_sec = (ex.solving_speed or 0) / 1000

                    words_html += f'<li class="{outcome_class}">{word} → {trans} <span style="color:#999">({speed_sec:.1f}s, {outcome})</span></li>'

            html += f"""
            <div class="session-card">
                <div class="session-header">
                    <span class="session-time">{session.start_time.strftime('%H:%M')}</span>
                    <span class="session-lang">{session_lang or "?"}</span>
                    <span class="session-duration">{duration_min:.1f} min | {len(exercises)} words</span>
                </div>
                <ul class="word-list">
                    {words_html}
                </ul>
            </div>
"""
    else:
        html += '<p style="color:#7f8c8d; text-align:center;">No exercise sessions in this period.</p>'

    html += """
        </div>

        <div class="section">
            <h2>Reading Sessions</h2>
"""

    if reading_sessions:
        for session in reading_sessions:
            duration_min = (session.duration or 0) / 60000
            article = session.article
            article_title = article.title if article else "Unknown article"
            article_lang = (
                article.language.code.upper() if article and article.language else "?"
            )

            # Get translations made for this article
            article_translations = []
            if article and article.source_id:
                article_bookmarks = (
                    Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
                    .filter(UserWord.user_id == user_id)
                    .filter(Bookmark.source_id == article.source_id)
                    .filter(Bookmark.time >= start)
                    .filter(Bookmark.time < end)
                    .all()
                )
                for bm in article_bookmarks:
                    if bm.user_word and bm.user_word.meaning:
                        origin = bm.user_word.meaning.origin
                        translation = bm.user_word.meaning.translation
                        article_translations.append(
                            {
                                "word": origin.content if origin else "?",
                                "translation": (
                                    translation.content if translation else "?"
                                ),
                            }
                        )

            words_html = ""
            if article_translations:
                words_html = '<ul class="word-list" style="margin-top:10px;">'
                for t in article_translations:
                    words_html += f'<li>{t["word"]} → {t["translation"]}</li>'
                words_html += "</ul>"

            translation_count = (
                f" | {len(article_translations)} words" if article_translations else ""
            )

            html += f"""
            <div class="session-card">
                <div class="session-header">
                    <span class="session-time">{session.start_time.strftime('%H:%M')}</span>
                    <span class="session-lang">{article_lang}</span>
                    <span class="session-duration">{duration_min:.1f} min{translation_count}</span>
                </div>
                <p style="margin:0;"><strong>{article_title}</strong></p>
                {words_html}
            </div>
"""
    else:
        html += '<p style="color:#7f8c8d; text-align:center;">No reading sessions in this period.</p>'

    html += """
        </div>

        <div class="section">
            <h2>Audio Lessons</h2>
"""

    if audio_lessons:
        for lesson in audio_lessons:
            duration_min = (lesson.duration_seconds or 0) / 60
            lesson_lang = lesson.language.code.upper() if lesson.language else "?"
            completed_time = (
                lesson.completed_at.strftime("%H:%M") if lesson.completed_at else "?"
            )

            html += f"""
            <div class="session-card">
                <div class="session-header">
                    <span class="session-time">{completed_time}</span>
                    <span class="session-lang">{lesson_lang}</span>
                    <span class="session-duration">{duration_min:.1f} min</span>
                </div>
                <p style="margin:0;"><strong>Daily Lesson ({lesson.meaning_count} words)</strong></p>
            </div>
"""
    else:
        html += '<p style="color:#7f8c8d; text-align:center;">No audio lessons in this period.</p>'

    html += """
        </div>
"""

    # Filter bookmarks to only show those NOT associated with any reading session article
    # (those without a source_id, i.e., translations made outside of articles)
    other_bookmarks = [bm for bm in bookmarks if not bm.source_id]

    if other_bookmarks:
        html += """
        <div class="section">
            <h2>Other Translations</h2>
"""
        # Group translations by language
        translations_by_lang = defaultdict(list)
        for bm in other_bookmarks:
            if bm.user_word and bm.user_word.meaning:
                origin = bm.user_word.meaning.origin
                translation = bm.user_word.meaning.translation
                lang_code = (
                    origin.language.code.upper() if origin and origin.language else "?"
                )
                translations_by_lang[lang_code].append(
                    {
                        "word": origin.content if origin else "?",
                        "translation": translation.content if translation else "?",
                        "time": bm.time,
                    }
                )

        for lang_code, translations in sorted(translations_by_lang.items()):
            html += f"""
            <div class="session-card">
                <div class="session-header">
                    <span class="session-lang">{lang_code}</span>
                    <span class="session-duration">{len(translations)} words</span>
                </div>
                <ul class="word-list">
"""
            for t in translations:
                time_str = t["time"].strftime("%H:%M") if t["time"] else ""
                html += f'<li>{t["word"]} → {t["translation"]} <span style="color:#999">({time_str})</span></li>'
            html += """
                </ul>
            </div>
"""
        html += """
        </div>
"""

    html += f"""

        <p style="color:#7f8c8d; font-size:0.9em; margin-top:30px;">
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
            <a href="/user_stats/user/{user_id}?period={period}">JSON API</a>
        </p>
    </div>
</body>
</html>"""

    return Response(html, mimetype="text/html")


@api.route("/user_stats/cohort/<int:cohort_id>/dashboard", methods=["GET"])
@cross_domain
@requires_session
@only_admins
def user_stats_cohort_dashboard(cohort_id):
    """HTML dashboard for cohort activity with teacher info."""
    period = request.args.get("period", "yesterday")
    start, end, period_label = get_period_range(period)

    cohort = Cohort.query.get(cohort_id)
    if not cohort:
        return Response("<h1>Cohort not found</h1>", status=404, mimetype="text/html")

    # Get teachers for this cohort
    teachers = cohort.get_teachers()
    teacher_names = (
        ", ".join(t.name for t in teachers) if teachers else "No teacher assigned"
    )
    teacher_emails = ", ".join(t.email for t in teachers) if teachers else ""

    # Get all students in the cohort
    students = cohort.get_students()
    student_ids = {s.id for s in students}

    # Collect activity for cohort members only
    users_by_language = defaultdict(list)

    for user in students:
        user_id = user.id
        exercise_stats = get_exercise_stats_for_user(user_id, start, end)
        reading_stats = get_reading_stats_for_user(user_id, start, end)
        browsing_stats = get_browsing_stats_for_user(user_id, start, end)
        translation_stats = get_translations_for_user(user_id, start, end)
        audio_stats = get_audio_lesson_stats_for_user(user_id, start, end)

        # Determine languages from activity
        active_languages = set()
        active_languages.update(exercise_stats["words_by_language"].keys())
        active_languages.update(reading_stats["articles_by_language"].keys())
        active_languages.update(browsing_stats["words_by_language"].keys())
        active_languages.update(translation_stats["by_language"].keys())
        active_languages.update(audio_stats["lessons_by_language"].keys())

        # If no activity, still show under cohort's default language
        if not active_languages:
            if cohort.language:
                active_languages = {cohort.language.code}
            else:
                active_languages = {"unknown"}

        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "exercise_duration_min": exercise_stats["duration_min"],
            "exercise_sessions": exercise_stats["session_count"],
            "exercise_words": exercise_stats["words_by_language"],
            "reading_duration_min": reading_stats["duration_min"],
            "articles_read": reading_stats["articles_by_language"],
            "browsing_duration_min": browsing_stats["duration_min"],
            "browsing_words": browsing_stats["words_by_language"],
            "translations": translation_stats["by_language"],
            "audio_lessons": audio_stats["lessons_by_language"],
            "audio_duration_min": audio_stats["duration_min"],
            "audio_duration_by_language": audio_stats["duration_by_language"],
            "languages": list(active_languages),
            "has_activity": (
                exercise_stats["session_count"] > 0
                or reading_stats["session_count"] > 0
                or browsing_stats["session_count"] > 0
                or translation_stats["total"] > 0
                or audio_stats["lesson_count"] > 0
            ),
        }

        for lang in active_languages:
            users_by_language[lang].append(user_data)

    # Calculate totals
    total_exercise_min = 0
    total_reading_min = 0
    total_browsing_min = 0
    total_audio_min = 0
    active_users = set()

    for lang_code, users in users_by_language.items():
        for u in users:
            if u["has_activity"]:
                active_users.add(u["id"])
            total_exercise_min += u["exercise_duration_min"]
            total_reading_min += u["reading_duration_min"]
            total_browsing_min += u["browsing_duration_min"]
            total_audio_min += u["audio_duration_by_language"].get(lang_code, 0)

    # Get language names
    languages = {l.code: l.name for l in Language.available_languages()}

    # Sort languages by activity
    sorted_languages = sorted(
        users_by_language.items(),
        key=lambda x: sum(
            u["exercise_duration_min"]
            + u["reading_duration_min"]
            + u["browsing_duration_min"]
            for u in x[1]
        ),
        reverse=True,
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{cohort.name} - Cohort Stats</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #2c3e50; margin-bottom: 5px; }}
        .subtitle {{ color: #7f8c8d; margin-bottom: 20px; }}
        .back-link {{ color: #3498db; text-decoration: none; margin-bottom: 15px; display: inline-block; }}
        .back-link:hover {{ text-decoration: underline; }}
        .teacher-info {{
            background: #e8f4f8; padding: 15px; border-radius: 8px;
            margin-bottom: 20px; border-left: 4px solid #3498db;
        }}
        .teacher-info h3 {{ margin: 0 0 5px 0; color: #2c3e50; }}
        .teacher-info p {{ margin: 0; color: #555; }}
        .summary {{
            display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap;
        }}
        .stat-card {{
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 150px;
        }}
        .stat-card .number {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .stat-card .label {{ color: #7f8c8d; font-size: 0.9em; }}
        .section {{
            background: white; padding: 20px; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{ margin-top: 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        th.group-header {{
            text-align: center;
            background: #e8f4f8;
            border-bottom: 2px solid #3498db;
            font-size: 0.95em;
        }}
        th.sub-header {{
            font-size: 0.85em;
            color: #666;
            font-weight: 500;
        }}
        tr:hover {{ background: #f8f9fa; }}
        .lang-code {{
            display: inline-block; padding: 2px 8px;
            background: #3498db; color: white; border-radius: 4px;
            font-weight: bold; font-size: 0.9em;
        }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block; padding: 8px 16px; margin-right: 10px;
            background: #3498db; color: white; text-decoration: none;
            border-radius: 4px;
        }}
        .nav a:hover {{ background: #2980b9; }}
        .nav a.active {{ background: #2c3e50; }}
        .user-link {{ color: #3498db; text-decoration: none; }}
        .user-link:hover {{ text-decoration: underline; }}
        .no-activity {{ color: #bdc3c7; }}
        .duration {{ font-family: monospace; }}
        .inactive-row {{ background: #fafafa; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/user_stats/dashboard?period={period}" class="back-link">&larr; Back to overview</a>
        <h1>{cohort.name}</h1>
        <p class="subtitle">
            Invite code: <strong>{cohort.inv_code}</strong> |
            {period_label} ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})
        </p>

        <div class="teacher-info">
            <h3>Teacher</h3>
            <p><strong>{teacher_names}</strong></p>
            {f'<p style="font-size:0.9em; color:#666;">{teacher_emails}</p>' if teacher_emails else ''}
        </div>

        <div class="nav">
            <a href="?period=today" {"class='active'" if period == "today" else ""}>Today</a>
            <a href="?period=yesterday" {"class='active'" if period == "yesterday" else ""}>Yesterday</a>
            <a href="?period=2days" {"class='active'" if period == "2days" else ""}>2 days ago</a>
            <a href="?period=week" {"class='active'" if period == "week" else ""}>Last 7 days</a>
            <a href="?period=month" {"class='active'" if period == "month" else ""}>Last 30 days</a>
        </div>

        <div class="summary">
            <div class="stat-card">
                <div class="number">{len(students)}</div>
                <div class="label">Total Students</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(active_users)}</div>
                <div class="label">Active Students</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_exercise_min, 0):.0f}</div>
                <div class="label">Exercise Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_reading_min, 0):.0f}</div>
                <div class="label">Reading Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_browsing_min, 0):.0f}</div>
                <div class="label">Browsing Minutes</div>
            </div>
            <div class="stat-card">
                <div class="number">{round(total_audio_min, 0):.0f}</div>
                <div class="label">Audio Minutes</div>
            </div>
        </div>
"""

    for lang_code, users in sorted_languages:
        lang_name = languages.get(lang_code, lang_code.upper())

        # Sort users: active first, then by total activity
        sorted_users = sorted(
            users,
            key=lambda u: (
                u["has_activity"],
                u["exercise_duration_min"]
                + u["reading_duration_min"]
                + u["browsing_duration_min"],
            ),
            reverse=True,
        )

        html += f"""
        <div class="section">
            <h2><span class="lang-code">{lang_code.upper()}</span> {lang_name}</h2>
            <table>
                <tr>
                    <th rowspan="2">Student</th>
                    <th colspan="2" class="group-header">Exercises</th>
                    <th colspan="2" class="group-header">Reading</th>
                    <th colspan="2" class="group-header">Browsing</th>
                    <th colspan="2" class="group-header">Audio</th>
                </tr>
                <tr>
                    <th class="sub-header">Time</th>
                    <th class="sub-header">Words</th>
                    <th class="sub-header">Time</th>
                    <th class="sub-header">Articles</th>
                    <th class="sub-header">Time</th>
                    <th class="sub-header">Words</th>
                    <th class="sub-header">Count</th>
                    <th class="sub-header">Time</th>
                </tr>
"""

        for user in sorted_users:
            exercise_words = user["exercise_words"].get(lang_code, 0)
            articles = user["articles_read"].get(lang_code, 0)
            browsing_words = user["browsing_words"].get(lang_code, 0)
            audio_lessons = user["audio_lessons"].get(lang_code, 0)
            audio_duration = user["audio_duration_by_language"].get(lang_code, 0)

            row_class = "" if user["has_activity"] else "inactive-row"
            exercise_class = "" if user["exercise_duration_min"] > 0 else "no-activity"
            reading_class = "" if user["reading_duration_min"] > 0 else "no-activity"
            browsing_class = "" if user["browsing_duration_min"] > 0 else "no-activity"
            audio_class = "" if audio_lessons > 0 else "no-activity"

            html += f"""
                <tr class="{row_class}">
                    <td><a href="/user_stats/user/{user['id']}/dashboard?period={period}" class="user-link">{user['name']}</a></td>
                    <td class="{exercise_class} duration">{user['exercise_duration_min']:.1f} min</td>
                    <td class="{exercise_class}">{exercise_words}</td>
                    <td class="{reading_class} duration">{user['reading_duration_min']:.1f} min</td>
                    <td class="{reading_class}">{articles}</td>
                    <td class="{browsing_class} duration">{user['browsing_duration_min']:.1f} min</td>
                    <td class="{browsing_class}">{browsing_words}</td>
                    <td class="{audio_class}">{audio_lessons}</td>
                    <td class="{audio_class} duration">{audio_duration:.1f} min</td>
                </tr>
"""

        html += """
            </table>
        </div>
"""

    if not users_by_language:
        html += """
        <div class="section">
            <p style="text-align:center; color:#7f8c8d; padding: 40px;">
                No students in this cohort.
            </p>
        </div>
"""

    html += f"""
        <p style="color:#7f8c8d; font-size:0.9em; margin-top:30px;">
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>"""

    return Response(html, mimetype="text/html")


@api.route("/admin", methods=["GET"])
@cross_domain
def admin_index():
    """
    Main admin entry point.
    Redirects to dashboard if logged in as admin, otherwise to login page.
    """
    session_uuid = request.cookies.get("chocolatechip")
    if session_uuid:
        session_object = Session.find(session_uuid)
        if session_object:
            user = User.find_by_id(session_object.user_id)
            if user and user.is_admin:
                return redirect("/user_stats/dashboard")

    return redirect("/admin/login")


@api.route("/admin/login", methods=["GET"])
@cross_domain
def admin_login_form():
    """Show admin login form."""
    error = request.args.get("error", "")
    error_html = (
        f'<p style="color:#e74c3c; margin-bottom:15px;">{error}</p>' if error else ""
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - Zeeguu</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }}
        .login-box {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
        }}
        h1 {{
            margin: 0 0 20px 0;
            color: #2c3e50;
            font-size: 1.5em;
        }}
        label {{
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 1em;
            box-sizing: border-box;
        }}
        input:focus {{
            outline: none;
            border-color: #3498db;
        }}
        button {{
            width: 100%;
            padding: 12px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 1em;
            cursor: pointer;
        }}
        button:hover {{
            background: #2980b9;
        }}
        .subtitle {{
            color: #7f8c8d;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="login-box">
        <h1>Admin Dashboard</h1>
        <p class="subtitle">Sign in to access admin dashboards</p>
        {error_html}
        <form method="POST" action="/admin/login">
            <label for="email">Email</label>
            <input type="email" id="email" name="email" required autofocus>

            <label for="password">Password</label>
            <input type="password" id="password" name="password" required>

            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@api.route("/admin/login", methods=["POST"])
@cross_domain
def admin_login_submit():
    """Process admin login and redirect to dashboard."""
    email = request.form.get("email", "")
    password = request.form.get("password", "")

    # Authenticate user
    user = User.authorize(email, password)

    if not user:
        return redirect("/admin/login?error=Invalid+credentials")

    if not user.is_admin:
        return redirect("/admin/login?error=Not+authorized+as+admin")

    # Create session
    session = Session.create_for_user(user)
    db_session.add(session)
    db_session.commit()

    # Set cookie and redirect to dashboard
    response = make_response(redirect("/user_stats/dashboard"))
    response.set_cookie("chocolatechip", str(session.uuid))
    return response


@api.route("/user_stats/platform/<int:platform_id>/dashboard", methods=["GET"])
@cross_domain
@requires_session
@only_admins
def user_stats_platform_dashboard(platform_id):
    """HTML dashboard showing users who used a specific platform."""
    period = request.args.get("period", "week")
    start, end, label = get_period_range(period)

    platform_name = PLATFORM_NAMES.get(platform_id, f"Platform {platform_id}")

    # Get users for this platform
    from sqlalchemy import func
    user_ids = (
        db_session.query(func.distinct(UserActivityData.user_id))
        .filter(UserActivityData.time >= start)
        .filter(UserActivityData.time < end)
        .filter(UserActivityData.platform == platform_id)
        .all()
    )
    user_ids = [uid[0] for uid in user_ids]

    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{platform_name} Users - {label}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        .back-link {{ margin-bottom: 20px; }}
        .back-link a {{ color: #3498db; text-decoration: none; }}
        .back-link a:hover {{ text-decoration: underline; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #2c3e50; }}
        tr:hover {{ background: #f8f9fa; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .count {{ color: #7f8c8d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="back-link"><a href="/user_stats/dashboard?period={period}">&larr; Back to Dashboard</a></div>
        <h1>{platform_name} Users</h1>
        <p class="count">{len(users)} users active on {platform_name} during {label}</p>
        <table>
            <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Cohort</th>
            </tr>
"""

    for user in sorted(users, key=lambda u: u.name.lower() if u.name else ""):
        cohort_name, cohort_id = get_user_cohort_info(user)
        cohort_link = f'<a href="/user_stats/cohort/{cohort_id}/dashboard?period={period}">{cohort_name}</a>' if cohort_id else cohort_name

        html += f"""
            <tr>
                <td><a href="/user_stats/user/{user.id}/dashboard?period={period}">{user.name or 'N/A'}</a></td>
                <td>{user.email}</td>
                <td>{cohort_link}</td>
            </tr>
"""

    html += """
        </table>
    </div>
</body>
</html>"""

    return Response(html, content_type="text/html")


def _compute_active_users_for_month(month_start, month_end):
    """Compute active user count for a specific month range."""
    from sqlalchemy import func, distinct, union_all

    exercise_users = (
        db_session.query(distinct(UserExerciseSession.user_id))
        .filter(UserExerciseSession.start_time >= month_start)
        .filter(UserExerciseSession.start_time < month_end)
    )

    reading_users = (
        db_session.query(distinct(UserReadingSession.user_id))
        .filter(UserReadingSession.start_time >= month_start)
        .filter(UserReadingSession.start_time < month_end)
    )

    browsing_users = (
        db_session.query(distinct(UserBrowsingSession.user_id))
        .filter(UserBrowsingSession.start_time >= month_start)
        .filter(UserBrowsingSession.start_time < month_end)
    )

    audio_users = (
        db_session.query(distinct(DailyAudioLesson.user_id))
        .filter(DailyAudioLesson.completed_at >= month_start)
        .filter(DailyAudioLesson.completed_at < month_end)
    )

    bookmark_users = (
        db_session.query(distinct(UserWord.user_id))
        .join(Bookmark, Bookmark.user_word_id == UserWord.id)
        .filter(Bookmark.time >= month_start)
        .filter(Bookmark.time < month_end)
    )

    all_users = union_all(
        exercise_users, reading_users, browsing_users, audio_users, bookmark_users
    ).subquery()

    from sqlalchemy import func, distinct
    return db_session.query(func.count(distinct(all_users.c[0]))).scalar() or 0


def get_monthly_active_users(months=12):
    """
    Get active user counts per month for the last N months.
    Uses caching: historical months are cached permanently,
    current month is refreshed every 6 hours.
    """
    from zeeguu.core.model import MonthlyActiveUsersCache

    now = datetime.now()
    current_year_month = now.strftime("%Y-%m")
    monthly_data = []

    # Get all cached data in one query
    cache = MonthlyActiveUsersCache.get_all_cached()

    for i in range(months):
        # Calculate month boundaries
        if i == 0:
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_end = now
        else:
            # Go back i months
            year = now.year
            month = now.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_start = datetime(year, month, 1)
            # End is start of next month
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1
            month_end = datetime(next_year, next_month, 1)

        year_month = month_start.strftime("%Y-%m")
        is_current_month = (year_month == current_year_month)

        # Check cache
        cached = cache.get(year_month)
        use_cache = False

        if cached:
            if is_current_month:
                # For current month, use cache if less than 6 hours old
                cache_age = now - cached.computed_at
                if cache_age.total_seconds() < 6 * 3600:
                    use_cache = True
            else:
                # Historical months: always use cache
                use_cache = True

        if use_cache:
            active_users = cached.active_users
        else:
            # Compute and cache
            active_users = _compute_active_users_for_month(month_start, month_end)
            MonthlyActiveUsersCache.set_cached(db_session, year_month, active_users)

        monthly_data.append({
            "month": year_month,
            "month_label": month_start.strftime("%b %Y"),
            "active_users": active_users,
        })

    # Reverse to show oldest first
    return list(reversed(monthly_data))


@api.route("/stats/monthly_active_users", methods=["GET"])
@cross_domain
def monthly_active_users_page():
    """
    Public page showing monthly active users.
    Embeddable on the homepage.
    """
    months = min(int(request.args.get("months", 12)), 24)
    monthly_data = get_monthly_active_users(months)

    # Calculate max for chart scaling
    max_users = max((m["active_users"] for m in monthly_data), default=1)

    # Generate chart bars
    chart_bars = ""
    for m in monthly_data:
        height_pct = (m["active_users"] / max_users * 100) if max_users > 0 else 0
        chart_bars += f"""
            <div class="bar-container">
                <div class="bar" style="height: {height_pct}%;">
                    <span class="bar-value">{m['active_users']}</span>
                </div>
                <span class="bar-label">{m['month_label'][:3]}</span>
            </div>
"""

    # Generate table rows
    table_rows = ""
    for m in reversed(monthly_data):  # Most recent first in table
        table_rows += f"""
            <tr>
                <td>{m['month_label']}</td>
                <td class="count">{m['active_users']}</td>
            </tr>
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Monthly Active Users - Zeeguu</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f8f9fa;
            color: #333;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 5px;
            font-size: 1.5em;
        }}
        .subtitle {{
            color: #7f8c8d;
            margin-bottom: 25px;
            font-size: 0.95em;
        }}
        .chart-section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            margin-bottom: 20px;
        }}
        .chart {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            height: 200px;
            padding: 10px 0;
            border-bottom: 2px solid #ecf0f1;
        }}
        .bar-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
            height: 100%;
        }}
        .bar {{
            width: 70%;
            max-width: 40px;
            background: linear-gradient(180deg, #3498db 0%, #2980b9 100%);
            border-radius: 4px 4px 0 0;
            position: relative;
            min-height: 2px;
            display: flex;
            justify-content: center;
            transition: height 0.3s ease;
        }}
        .bar:hover {{
            background: linear-gradient(180deg, #5dade2 0%, #3498db 100%);
        }}
        .bar-value {{
            position: absolute;
            top: -22px;
            font-size: 11px;
            font-weight: 600;
            color: #2c3e50;
        }}
        .bar-label {{
            margin-top: 8px;
            font-size: 11px;
            color: #7f8c8d;
        }}
        .table-section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }}
        .table-section h2 {{
            margin: 0 0 15px 0;
            font-size: 1.1em;
            color: #2c3e50;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #555;
        }}
        td.count {{
            font-weight: 600;
            color: #3498db;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .footer {{
            margin-top: 20px;
            text-align: center;
            color: #95a5a6;
            font-size: 0.85em;
        }}
        .footer a {{
            color: #3498db;
            text-decoration: none;
        }}

        /* Embed mode - minimal styling */
        body.embed {{
            background: transparent;
            padding: 10px;
        }}
        body.embed h1, body.embed .subtitle, body.embed .footer {{
            display: none;
        }}
        body.embed .chart-section, body.embed .table-section {{
            box-shadow: none;
            border: 1px solid #ecf0f1;
        }}
    </style>
</head>
<body{"class='embed'" if request.args.get('embed') else ''}>
    <div class="container">
        <h1>Monthly Active Users</h1>
        <p class="subtitle">Users with any learning activity (exercises, reading, browsing, audio lessons, or translations)</p>

        <div class="chart-section">
            <div class="chart">
{chart_bars}
            </div>
        </div>

        <div class="table-section">
            <h2>Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Month</th>
                        <th>Active Users</th>
                    </tr>
                </thead>
                <tbody>
{table_rows}
                </tbody>
            </table>
        </div>

        <p class="footer">
            Data from <a href="https://zeeguu.org">Zeeguu</a> |
            Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </p>
    </div>
</body>
</html>"""

    return Response(html, mimetype="text/html")
