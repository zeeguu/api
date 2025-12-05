"""
User activity statistics endpoint for monitoring daily user engagement.
Shows exercise sessions, reading sessions, and word progress grouped by language.
Replaces frequent email notifications with a consolidated dashboard view.
"""

from datetime import datetime, timedelta
from collections import defaultdict

from flask import request, Response
from sqlalchemy import func, and_

from . import api, db_session
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session, only_admins
from zeeguu.core.model import User, Article, Language
from zeeguu.core.model.user_exercise_session import UserExerciseSession
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.user_cohort_map import UserCohortMap
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.bookmark import Bookmark


def get_period_range(period: str):
    """Get start and end datetime for the given period."""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "week":
        start = today_start - timedelta(days=7)
        end = today_start
        label = "Last 7 days"
    elif period == "2days":
        start = today_start - timedelta(days=2)
        end = today_start - timedelta(days=1)
        label = "Two days ago"
    else:  # yesterday (default)
        start = today_start - timedelta(days=1)
        end = today_start
        label = "Yesterday"

    return start, end, label


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
        UserExerciseSession.query
        .filter(UserExerciseSession.user_id == user_id)
        .filter(UserExerciseSession.start_time >= start)
        .filter(UserExerciseSession.start_time < end)
        .all()
    )

    total_duration_ms = sum(s.duration or 0 for s in sessions)
    session_count = len(sessions)

    # Get unique words practiced and language info
    words_by_language = defaultdict(set)

    for session in sessions:
        exercises = (
            Exercise.query
            .filter(Exercise.session_id == session.id)
            .all()
        )
        for ex in exercises:
            if ex.user_word and ex.user_word.meaning and ex.user_word.meaning.origin:
                lang = ex.user_word.meaning.origin.language
                if lang:
                    words_by_language[lang.code].add(ex.user_word_id)

    return {
        "session_count": session_count,
        "duration_ms": total_duration_ms,
        "duration_min": round(total_duration_ms / 60000, 1),
        "words_by_language": {lang: len(words) for lang, words in words_by_language.items()},
        "sessions": sessions,
    }


def get_reading_stats_for_user(user_id, start, end):
    """Get reading session stats for a user in the given period."""
    sessions = (
        UserReadingSession.query
        .filter(UserReadingSession.user_id == user_id)
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
        "articles_by_language": {lang: len(arts) for lang, arts in articles_by_language.items()},
        "sessions": sessions,
    }


def get_translations_for_user(user_id, start, end):
    """Get translations/bookmarks made by user in the given period."""
    from zeeguu.core.model.bookmark import Bookmark

    bookmarks = (
        Bookmark.query
        .join(UserWord, Bookmark.user_word_id == UserWord.id)
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

    # Combine unique user IDs from all activity types
    active_user_ids = (
        set(uid for (uid,) in exercise_user_ids) |
        set(uid for (uid,) in reading_user_ids) |
        set(uid for (uid,) in bookmark_user_ids)
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
        translation_stats = get_translations_for_user(user_id, start, end)

        # Determine languages from activity
        active_languages = set()
        active_languages.update(exercise_stats["words_by_language"].keys())
        active_languages.update(reading_stats["articles_by_language"].keys())
        active_languages.update(translation_stats["by_language"].keys())

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
            "translations": translation_stats["by_language"],
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
        }
    }

    seen_users = set()

    for lang_code, users in users_by_language.items():
        lang_exercise_min = sum(u["exercise_duration_min"] for u in users)
        lang_reading_min = sum(u["reading_duration_min"] for u in users)

        result["by_language"][lang_code] = {
            "user_count": len(users),
            "exercise_minutes": round(lang_exercise_min, 1),
            "reading_minutes": round(lang_reading_min, 1),
            "users": sorted(users, key=lambda u: u["exercise_duration_min"], reverse=True),
        }

        result["summary"]["total_exercise_minutes"] += lang_exercise_min
        result["summary"]["total_reading_minutes"] += lang_reading_min

        for u in users:
            seen_users.add(u["id"])

    result["summary"]["total_active_users"] = len(seen_users)
    result["summary"]["total_exercise_minutes"] = round(result["summary"]["total_exercise_minutes"], 1)
    result["summary"]["total_reading_minutes"] = round(result["summary"]["total_reading_minutes"], 1)

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
        UserExerciseSession.query
        .filter(UserExerciseSession.user_id == user_id)
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
                    words.append({
                        "word": origin.content if origin else "?",
                        "translation": translation.content if translation else "?",
                        "outcome": ex.outcome.outcome if ex.outcome else "?",
                        "solving_speed_ms": ex.solving_speed,
                    })

        exercise_session_details.append({
            "id": session.id,
            "start_time": session.start_time.isoformat(),
            "duration_min": round((session.duration or 0) / 60000, 1),
            "language": session_lang,
            "word_count": len(words),
            "words": words,
        })

    # Get reading sessions with details
    reading_sessions = (
        UserReadingSession.query
        .filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= start)
        .filter(UserReadingSession.start_time < end)
        .order_by(UserReadingSession.start_time.desc())
        .all()
    )

    reading_session_details = []
    for session in reading_sessions:
        article = session.article
        reading_session_details.append({
            "id": session.id,
            "start_time": session.start_time.isoformat(),
            "duration_min": round((session.duration or 0) / 60000, 1),
            "article_id": session.article_id,
            "article_title": article.title if article else "Unknown",
            "article_language": article.language.code if article and article.language else None,
        })

    # Get translations/bookmarks
    bookmarks = (
        Bookmark.query
        .join(UserWord, Bookmark.user_word_id == UserWord.id)
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
            translation_details.append({
                "word": origin.content if origin else "?",
                "translation": translation.content if translation else "?",
                "time": bm.time.isoformat() if bm.time else None,
                "language": origin.language.code if origin and origin.language else None,
            })

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
            "exercise_minutes": round(sum(s["duration_min"] for s in exercise_session_details), 1),
            "reading_session_count": len(reading_session_details),
            "reading_minutes": round(sum(s["duration_min"] for s in reading_session_details), 1),
            "translation_count": len(translation_details),
        }
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

    # Calculate totals
    total_users = set()
    total_exercise_min = 0
    total_reading_min = 0

    for lang_code, users in users_by_language.items():
        for u in users:
            total_users.add(u["id"])
            total_exercise_min += u["exercise_duration_min"]
            total_reading_min += u["reading_duration_min"]

    # Get language names
    languages = {l.code: l.name for l in Language.available_languages()}

    # Sort languages by activity
    sorted_languages = sorted(
        users_by_language.items(),
        key=lambda x: sum(u["exercise_duration_min"] + u["reading_duration_min"] for u in x[1]),
        reverse=True
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
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
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
            <a href="?period=yesterday" {"class='active'" if period == "yesterday" else ""}>Yesterday</a>
            <a href="?period=2days" {"class='active'" if period == "2days" else ""}>2 days ago</a>
            <a href="?period=week" {"class='active'" if period == "week" else ""}>Last 7 days</a>
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
                <div class="number">{len(users_by_language)}</div>
                <div class="label">Languages</div>
            </div>
        </div>
"""

    for lang_code, users in sorted_languages:
        lang_name = languages.get(lang_code, lang_code.upper())
        lang_exercise_min = sum(u["exercise_duration_min"] for u in users)
        lang_reading_min = sum(u["reading_duration_min"] for u in users)

        # Sort users by total activity
        sorted_users = sorted(
            users,
            key=lambda u: u["exercise_duration_min"] + u["reading_duration_min"],
            reverse=True
        )

        html += f"""
        <div class="section">
            <h2><span class="lang-code">{lang_code.upper()}</span> {lang_name}</h2>
            <p style="color:#7f8c8d; margin-bottom:15px;">
                {len(users)} active users |
                {round(lang_exercise_min, 0):.0f} min exercises |
                {round(lang_reading_min, 0):.0f} min reading
            </p>
            <table>
                <tr>
                    <th>User</th>
                    <th>Cohort / Code</th>
                    <th>Exercises</th>
                    <th>Words</th>
                    <th>Reading</th>
                    <th>Articles</th>
                    <th>Translations</th>
                </tr>
"""

        for user in sorted_users:
            cohort_display = user["cohort_name"] or "—"
            exercise_words = user["exercise_words"].get(lang_code, 0)
            articles = user["articles_read"].get(lang_code, 0)
            translations = user["translations"].get(lang_code, 0)

            exercise_class = "" if user["exercise_duration_min"] > 0 else "no-activity"
            reading_class = "" if user["reading_duration_min"] > 0 else "no-activity"

            html += f"""
                <tr>
                    <td><a href="/user_stats/user/{user['id']}/dashboard?period={period}" class="user-link">{user['name']}</a></td>
                    <td><span class="cohort-badge">{cohort_display}</span></td>
                    <td class="{exercise_class} duration">{user['exercise_duration_min']:.1f} min</td>
                    <td class="{exercise_class}">{exercise_words}</td>
                    <td class="{reading_class} duration">{user['reading_duration_min']:.1f} min</td>
                    <td class="{reading_class}">{articles}</td>
                    <td>{translations}</td>
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

    return Response(html, mimetype='text/html')


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
        return Response("<h1>User not found</h1>", status=404, mimetype='text/html')

    cohort_name, cohort_id = get_user_cohort_info(user)

    # Get exercise sessions with details
    exercise_sessions = (
        UserExerciseSession.query
        .filter(UserExerciseSession.user_id == user_id)
        .filter(UserExerciseSession.start_time >= start)
        .filter(UserExerciseSession.start_time < end)
        .order_by(UserExerciseSession.start_time.desc())
        .all()
    )

    # Get reading sessions with details
    reading_sessions = (
        UserReadingSession.query
        .filter(UserReadingSession.user_id == user_id)
        .filter(UserReadingSession.start_time >= start)
        .filter(UserReadingSession.start_time < end)
        .order_by(UserReadingSession.start_time.desc())
        .all()
    )

    # Get translations/bookmarks
    bookmarks = (
        Bookmark.query
        .join(UserWord, Bookmark.user_word_id == UserWord.id)
        .filter(UserWord.user_id == user_id)
        .filter(Bookmark.time >= start)
        .filter(Bookmark.time < end)
        .order_by(Bookmark.time.desc())
        .all()
    )

    # Calculate totals
    total_exercise_min = sum((s.duration or 0) / 60000 for s in exercise_sessions)
    total_reading_min = sum((s.duration or 0) / 60000 for s in reading_sessions)

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
            <a href="?period=yesterday" {"class='active'" if period == "yesterday" else ""}>Yesterday</a>
            <a href="?period=2days" {"class='active'" if period == "2days" else ""}>2 days ago</a>
            <a href="?period=week" {"class='active'" if period == "week" else ""}>Last 7 days</a>
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
                    outcome_class = "word-correct" if outcome == "C" else "word-incorrect" if outcome == "W" else ""
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
            article_lang = article.language.code.upper() if article and article.language else "?"

            html += f"""
            <div class="session-card">
                <div class="session-header">
                    <span class="session-time">{session.start_time.strftime('%H:%M')}</span>
                    <span class="session-lang">{article_lang}</span>
                    <span class="session-duration">{duration_min:.1f} min</span>
                </div>
                <p style="margin:0;"><strong>{article_title}</strong></p>
            </div>
"""
    else:
        html += '<p style="color:#7f8c8d; text-align:center;">No reading sessions in this period.</p>'

    html += """
        </div>

        <div class="section">
            <h2>Translations</h2>
"""

    if bookmarks:
        # Group translations by language
        translations_by_lang = defaultdict(list)
        for bm in bookmarks:
            if bm.user_word and bm.user_word.meaning:
                origin = bm.user_word.meaning.origin
                translation = bm.user_word.meaning.translation
                lang_code = origin.language.code.upper() if origin and origin.language else "?"
                translations_by_lang[lang_code].append({
                    "word": origin.content if origin else "?",
                    "translation": translation.content if translation else "?",
                    "time": bm.time,
                })

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
                time_str = t["time"].strftime('%H:%M') if t["time"] else ""
                html += f'<li>{t["word"]} → {t["translation"]} <span style="color:#999">({time_str})</span></li>'
            html += """
                </ul>
            </div>
"""
    else:
        html += '<p style="color:#7f8c8d; text-align:center;">No translations in this period.</p>'

    html += f"""
        </div>

        <p style="color:#7f8c8d; font-size:0.9em; margin-top:30px;">
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
            <a href="/user_stats/user/{user_id}?period={period}">JSON API</a>
        </p>
    </div>
</body>
</html>"""

    return Response(html, mimetype='text/html')
