"""
Crawl statistics endpoint for monitoring daily crawler performance.
Shows articles crawled per language, feed, and topic.
"""

from datetime import datetime, timedelta

from flask import request
from sqlalchemy import func, and_

from . import api, db_session
from zeeguu.api.utils.route_wrappers import cross_domain
from zeeguu.core.model import Article, Feed, Language, Topic
from zeeguu.core.model.article_topic_map import ArticleTopicMap


@api.route("/crawl_stats", methods=["GET"])
@cross_domain
def crawl_stats():
    """
    Get crawl statistics for today (or specified number of days).

    Query params:
        days: Number of days to look back (default: 1 = today only)

    Returns JSON with:
        - by_language: Articles per language
        - by_feed: Articles per feed (grouped by language)
        - by_topic: Simplified articles per topic
        - summary: Overall totals
    """
    days = int(request.args.get("days", 1))
    cutoff = datetime.now() - timedelta(days=days)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    result = {
        "period": {
            "days": days,
            "since": cutoff.isoformat(),
            "today_start": today_start.isoformat(),
        },
        "by_language": {},
        "by_feed": {},
        "by_topic": {},
        "summary": {
            "total_articles": 0,
            "total_simplified": 0,
            "total_feeds_with_articles": 0,
        }
    }

    # Get all available languages
    languages = Language.available_languages()

    for language in languages:
        # Count original articles per language (parent_article_id is NULL)
        article_count = (
            db_session.query(func.count(Article.id))
            .filter(Article.language_id == language.id)
            .filter(Article.published_time >= cutoff)
            .filter(Article.broken == 0)
            .filter(Article.parent_article_id == None)
            .scalar() or 0
        )

        # Count simplified articles per language (parent_article_id is NOT NULL)
        simplified_count = (
            db_session.query(func.count(Article.id))
            .filter(Article.language_id == language.id)
            .filter(Article.published_time >= cutoff)
            .filter(Article.parent_article_id != None)
            .scalar() or 0
        )

        if article_count > 0 or simplified_count > 0:
            result["by_language"][language.code] = {
                "name": language.name,
                "articles": article_count,
                "simplified": simplified_count,
            }
            result["summary"]["total_articles"] += article_count
            result["summary"]["total_simplified"] += simplified_count

        # Get feeds for this language with article counts (original articles only)
        feeds_with_counts = (
            db_session.query(
                Feed.id,
                Feed.title,
                func.count(Article.id).label("article_count")
            )
            .join(Article, Article.feed_id == Feed.id)
            .filter(Feed.language_id == language.id)
            .filter(Article.published_time >= cutoff)
            .filter(Article.broken == 0)
            .filter(Article.parent_article_id == None)
            .group_by(Feed.id, Feed.title)
            .order_by(func.count(Article.id).desc())
            .all()
        )

        if feeds_with_counts:
            result["by_feed"][language.code] = []
            for feed_id, feed_title, count in feeds_with_counts:
                result["by_feed"][language.code].append({
                    "id": feed_id,
                    "title": feed_title,
                    "articles": count,
                })
                result["summary"]["total_feeds_with_articles"] += 1

    # Get simplified articles by topic (today only for daily cap tracking)
    # Join: SimplifiedArticle -> Parent Article -> ArticleTopicMap -> Topic
    # Simplified articles have parent_article_id set
    ParentArticle = db_session.query(Article).subquery()

    topic_counts = (
        db_session.query(
            Topic.id,
            Topic.title,
            func.count(Article.id).label("count")
        )
        .join(ParentArticle, Article.parent_article_id == ParentArticle.c.id)
        .join(ArticleTopicMap, ArticleTopicMap.article_id == ParentArticle.c.id)
        .join(Topic, Topic.id == ArticleTopicMap.topic_id)
        .filter(Article.published_time >= today_start)
        .filter(Article.parent_article_id != None)
        .group_by(Topic.id, Topic.title)
        .order_by(func.count(Article.id).desc())
        .all()
    )

    from zeeguu.core.content_retriever.article_downloader import MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY

    for topic_id, topic_title, count in topic_counts:
        result["by_topic"][topic_title] = {
            "id": topic_id,
            "simplified_today": count,
            "daily_cap_per_lang": MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY,
        }

    return result


@api.route("/crawl_stats/today", methods=["GET"])
@cross_domain
def crawl_stats_today():
    """Shortcut for today's stats only."""
    return crawl_stats()


@api.route("/crawl_stats/week", methods=["GET"])
@cross_domain
def crawl_stats_week():
    """Get stats for the last 7 days."""
    # Temporarily set days param
    from flask import request
    request.args = {"days": "7"}
    return crawl_stats()


@api.route("/crawl_stats/dashboard", methods=["GET"])
@cross_domain
def crawl_stats_dashboard():
    """HTML dashboard showing crawl statistics."""
    from flask import Response

    days = int(request.args.get("days", 1))
    cutoff = datetime.now() - timedelta(days=days)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Gather stats
    languages = Language.available_languages()
    lang_stats = []
    feed_stats = {}
    total_articles = 0
    total_simplified = 0

    for language in languages:
        article_count = (
            db_session.query(func.count(Article.id))
            .filter(Article.language_id == language.id)
            .filter(Article.published_time >= cutoff)
            .filter(Article.broken == 0)
            .filter(Article.parent_article_id == None)
            .scalar() or 0
        )

        simplified_count = (
            db_session.query(func.count(Article.id))
            .filter(Article.language_id == language.id)
            .filter(Article.published_time >= cutoff)
            .filter(Article.parent_article_id != None)
            .scalar() or 0
        )

        if article_count > 0 or simplified_count > 0:
            lang_stats.append({
                "code": language.code,
                "name": language.name,
                "articles": article_count,
                "simplified": simplified_count,
            })
            total_articles += article_count
            total_simplified += simplified_count

            # Get feeds for this language with article counts
            feeds = (
                db_session.query(
                    Feed.id, Feed.title,
                    func.count(Article.id).label("count")
                )
                .join(Article, Article.feed_id == Feed.id)
                .filter(Feed.language_id == language.id)
                .filter(Article.published_time >= cutoff)
                .filter(Article.broken == 0)
                .filter(Article.parent_article_id == None)
                .group_by(Feed.id, Feed.title)
                .order_by(func.count(Article.id).desc())
                .limit(10)
                .all()
            )
            feed_stats[language.code] = feeds

            # Get topics per feed for this language
            feed_topic_stats = (
                db_session.query(
                    Feed.id,
                    Topic.title,
                    func.count(Article.id).label("count")
                )
                .join(Article, Article.feed_id == Feed.id)
                .join(ArticleTopicMap, ArticleTopicMap.article_id == Article.id)
                .join(Topic, Topic.id == ArticleTopicMap.topic_id)
                .filter(Feed.language_id == language.id)
                .filter(Article.published_time >= cutoff)
                .filter(Article.broken == 0)
                .filter(Article.parent_article_id == None)
                .group_by(Feed.id, Topic.title)
                .all()
            )
            # Group by feed_id
            from collections import defaultdict
            topics_by_feed = defaultdict(list)
            for feed_id, topic_title, count in feed_topic_stats:
                topics_by_feed[feed_id].append((topic_title, count))
            feed_stats[f"{language.code}_topics"] = topics_by_feed

    # Get topic stats per language
    from sqlalchemy.orm import aliased
    ParentArticle = aliased(Article)

    topic_stats_by_lang = (
        db_session.query(
            Language.code, Language.name,
            Topic.id, Topic.title,
            func.count(Article.id).label("count")
        )
        .join(ParentArticle, Article.parent_article_id == ParentArticle.id)
        .join(ArticleTopicMap, ArticleTopicMap.article_id == ParentArticle.id)
        .join(Topic, Topic.id == ArticleTopicMap.topic_id)
        .join(Language, ParentArticle.language_id == Language.id)
        .filter(Article.published_time >= today_start)
        .filter(Article.parent_article_id != None)
        .group_by(Language.code, Language.name, Topic.id, Topic.title)
        .order_by(Language.name, func.count(Article.id).desc())
        .all()
    )

    from zeeguu.core.content_retriever.article_downloader import MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY

    # Sort languages by article count
    lang_stats.sort(key=lambda x: x["articles"], reverse=True)

    # Build HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Zeeguu Crawl Stats</title>
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
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        .bar {{
            background: #3498db; height: 20px; border-radius: 3px;
            transition: width 0.3s;
        }}
        .bar-container {{ background: #ecf0f1; border-radius: 3px; width: 200px; }}
        .cap-reached {{ color: #e74c3c; font-weight: bold; }}
        .cap-ok {{ color: #27ae60; }}
        .lang-code {{
            display: inline-block; padding: 2px 8px;
            background: #3498db; color: white; border-radius: 4px;
            font-weight: bold; font-size: 0.9em;
        }}
        .feed-list {{ font-size: 0.9em; color: #7f8c8d; }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{
            display: inline-block; padding: 8px 16px; margin-right: 10px;
            background: #3498db; color: white; text-decoration: none;
            border-radius: 4px;
        }}
        .nav a:hover {{ background: #2980b9; }}
        .nav a.active {{ background: #2c3e50; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Zeeguu Crawl Statistics</h1>
        <p class="subtitle">
            {f"Last {days} day{'s' if days > 1 else ''}" if days > 1 else "Today"}
            (since {cutoff.strftime('%Y-%m-%d %H:%M')})
        </p>

        <div class="nav">
            <a href="?days=1" {"class='active'" if days == 1 else ""}>Today</a>
            <a href="?days=7" {"class='active'" if days == 7 else ""}>Last 7 days</a>
            <a href="?days=30" {"class='active'" if days == 30 else ""}>Last 30 days</a>
        </div>

        <div class="summary">
            <div class="stat-card">
                <div class="number">{total_articles}</div>
                <div class="label">Articles Crawled</div>
            </div>
            <div class="stat-card">
                <div class="number">{total_simplified}</div>
                <div class="label">Simplified Today</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(lang_stats)}</div>
                <div class="label">Active Languages</div>
            </div>
            <div class="stat-card">
                <div class="number">{MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY}</div>
                <div class="label">Cap/Topic/Lang</div>
            </div>
        </div>

        <div class="section">
            <h2>📚 By Language</h2>
            <table>
                <tr>
                    <th>Language</th>
                    <th>Articles</th>
                    <th>Simplified</th>
                    <th style="width:220px">Distribution</th>
                </tr>"""

    max_articles = max([l["articles"] for l in lang_stats]) if lang_stats else 1
    for lang in lang_stats:
        bar_width = int((lang["articles"] / max_articles) * 200) if max_articles > 0 else 0
        html += f"""
                <tr>
                    <td><span class="lang-code">{lang["code"].upper()}</span> {lang["name"]}</td>
                    <td>{lang["articles"]}</td>
                    <td>{lang["simplified"]}</td>
                    <td><div class="bar-container"><div class="bar" style="width:{bar_width}px"></div></div></td>
                </tr>"""

    html += f"""
            </table>
        </div>

        <div class="section">
            <h2>🏷️ Simplified by Topic per Language (Today)</h2>
            <p style="color:#7f8c8d; margin-bottom:15px;">Daily cap: {MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY} simplified articles per topic per language</p>"""

    # Group topic stats by language
    from collections import defaultdict
    topics_by_lang = defaultdict(list)
    for lang_code, lang_name, topic_id, topic_title, count in topic_stats_by_lang:
        topics_by_lang[lang_code].append((lang_name, topic_id, topic_title, count))

    if topics_by_lang:
        for lang_code in sorted(topics_by_lang.keys()):
            topics = topics_by_lang[lang_code]
            lang_name = topics[0][0]  # Get language name from first entry
            html += f"""
            <h3><span class="lang-code">{lang_code.upper()}</span> {lang_name}</h3>
            <table>
                <tr>
                    <th>Topic</th>
                    <th>Simplified</th>
                    <th>Status</th>
                    <th style="width:220px">Progress</th>
                </tr>"""
            for _, topic_id, topic_title, count in topics:
                cap_reached = count >= MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY
                bar_width = min(int((count / MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY) * 200), 200)
                status_class = "cap-reached" if cap_reached else "cap-ok"
                status_text = "CAP REACHED" if cap_reached else f"{MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY - count} remaining"
                html += f"""
                <tr>
                    <td>{topic_title}</td>
                    <td>{count} / {MAX_SIMPLIFIED_PER_TOPIC_PER_LANGUAGE_PER_DAY}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td><div class="bar-container"><div class="bar" style="width:{bar_width}px; background: {'#e74c3c' if cap_reached else '#27ae60'}"></div></div></td>
                </tr>"""
            html += "</table>"
    else:
        html += """<p style="text-align:center; color:#7f8c8d">No simplified articles today</p>"""

    html += """
        </div>

        <div class="section">
            <h2>📰 Feeds by Language (with Topics)</h2>"""

    for lang in lang_stats:  # All languages with articles
        code = lang["code"]
        if code in feed_stats and feed_stats[code]:
            topics_by_feed = feed_stats.get(f"{code}_topics", {})
            html += f"""
            <h3><span class="lang-code">{code.upper()}</span> {lang["name"]}</h3>
            <table>
                <tr><th>Feed</th><th>Articles</th><th>Topics</th></tr>"""
            for feed_id, feed_title, count in feed_stats[code][:10]:
                # Get topics for this feed
                feed_topics = topics_by_feed.get(feed_id, [])
                if feed_topics:
                    # Sort by count descending and format as "Topic(count)"
                    topics_str = ", ".join([f"{t}({c})" for t, c in sorted(feed_topics, key=lambda x: -x[1])])
                else:
                    topics_str = "<span style='color:#999'>—</span>"
                html += f"""
                <tr>
                    <td>{feed_title}</td>
                    <td>{count}</td>
                    <td style="font-size:0.85em">{topics_str}</td>
                </tr>"""
            html += "</table>"

    html += f"""
        </div>

        <p style="color:#7f8c8d; font-size:0.9em; margin-top:30px;">
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
            <a href="/crawl_stats?days={days}">JSON API</a>
        </p>
    </div>
</body>
</html>"""

    return Response(html, mimetype='text/html')
