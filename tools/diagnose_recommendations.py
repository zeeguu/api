#!/usr/bin/env python
"""
Diagnostic script to understand why a user might not be seeing their subscribed topics.
Usage: python -m tools.diagnose_recommendations <user_email_or_id>
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import User, Article, TopicSubscription, TopicFilter
from zeeguu.core.model.user_article import UserArticle
from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.source import Source
from zeeguu.core.content_recommender import article_recommendations_for_user
from elasticsearch import Elasticsearch
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX


def diagnose_user(user_identifier):
    # Find user
    if user_identifier.isdigit():
        user = User.find_by_id(int(user_identifier))
    else:
        user = User.find(user_identifier)

    if not user:
        print(f"User not found: {user_identifier}")
        return

    print(f"\n{'='*60}")
    print(f"DIAGNOSIS FOR: {user.name} (ID: {user.id})")
    print(f"Learning: {user.learned_language.name}")
    print(f"{'='*60}\n")

    # 1. Topic Subscriptions
    print("1. TOPIC SUBSCRIPTIONS")
    print("-" * 40)
    subscriptions = TopicSubscription.all_for_user(user)
    if subscriptions:
        for sub in subscriptions:
            print(f"   + {sub.topic.title}")
    else:
        print("   (none - will see all topics)")

    # Topic Filters (excluded)
    filters = TopicFilter.all_for_user(user)
    if filters:
        print("\n   Excluded topics:")
        for f in filters:
            print(f"   - {f.topic.title}")
    print()

    # 2. Hidden Articles
    print("2. HIDDEN ARTICLES")
    print("-" * 40)
    hidden_articles = (
        UserArticle.query.filter_by(user=user)
        .filter(UserArticle.hidden.isnot(None))
        .all()
    )
    print(f"   Total hidden: {len(hidden_articles)}")

    # Count hidden articles by topic
    hidden_topics = {}
    if hidden_articles:
        for ua in hidden_articles:
            article = Article.find_by_id(ua.article_id)
            if article and article.topics:
                for topic_map in article.topics:
                    topic_name = topic_map.topic.title
                    hidden_topics[topic_name] = hidden_topics.get(topic_name, 0) + 1

    # Count TOTAL articles per topic for this language (from ES)
    print(f"\n   Articles per topic (hidden vs total available in {user.learned_language.name}):")
    print("   " + "-" * 55)

    from zeeguu.core.model.topic import Topic
    es = Elasticsearch(ES_CONN_STRING)

    all_topics = Topic.query.all()
    topic_stats = []

    for topic in all_topics:
        # Count total in ES for this language
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"language": user.learned_language.name}},
                        {"bool": {"should": [
                            {"match": {"topics": topic.title}},
                            {"match": {"topics_inferred": topic.title}}
                        ]}}
                    ]
                }
            }
        }
        try:
            res = es.count(index=ES_ZINDEX, body=query)
            total = res.get('count', 0)
        except:
            total = "?"

        hidden = hidden_topics.get(topic.title, 0)
        if total != "?" and total > 0:
            pct = f"({hidden*100//total}%)" if hidden > 0 else ""
            topic_stats.append((topic.title, hidden, total, pct))

    # Sort by hidden count descending
    for topic_name, hidden, total, pct in sorted(topic_stats, key=lambda x: -x[1]):
        if hidden > 0 or total > 50:  # Show if hidden any, or has significant articles
            print(f"      {topic_name:30} {hidden:4} hidden / {total:5} total {pct}")
    print()

    # 3. Ignored Sources
    print("3. IGNORED SOURCES (behavioral filtering)")
    print("-" * 40)
    ignored_source_ids = UserActivityData.get_sources_ignored_by_user(user)
    print(f"   Total ignored sources (articles scrolled past 2+ times): {len(ignored_source_ids)}")
    if ignored_source_ids:
        print("   Ignored articles (showing first 10):")
        for sid in ignored_source_ids[:10]:
            article = Article.query.filter_by(source_id=sid).first()
            if article:
                title = article.title[:50] + "..." if len(article.title) > 50 else article.title
                topics = ", ".join([tm.topic.title for tm in article.topics]) if article.topics else "(no topic)"
                print(f"      [{topics}] {title}")
    print()

    # 4. Test ES Query
    print("4. ELASTICSEARCH QUERY TEST")
    print("-" * 40)

    # Collect exclusions (same logic as endpoint)
    articles_to_exclude = [ua.article_id for ua in hidden_articles]
    print(f"   Articles to exclude: {len(articles_to_exclude)}")
    print(f"   Sources to exclude: {len(ignored_source_ids)}")

    try:
        content = article_recommendations_for_user(
            user,
            count=20,
            page=0,
            articles_to_exclude=articles_to_exclude
        )
        print(f"   ES query SUCCESS - returned {len(content)} items")

        if content:
            # Analyze topics in results
            result_topics = {}
            for item in content:
                if hasattr(item, 'topics') and item.topics:
                    for topic_map in item.topics:
                        topic_name = topic_map.topic.title
                        result_topics[topic_name] = result_topics.get(topic_name, 0) + 1

            print("   Topics in results:")
            for topic, count in sorted(result_topics.items(), key=lambda x: -x[1]):
                print(f"      {topic}: {count}")
        else:
            print("   WARNING: Query returned 0 results!")
            print("   This could trigger the DB fallback (no topic filter)!")

    except Exception as e:
        print(f"   ES query FAILED: {type(e).__name__}: {e}")
        print("   This WILL trigger the DB fallback (no topic filter)!")
    print()

    # 5. Check available articles for subscribed topics
    if subscriptions:
        print("5. AVAILABLE ARTICLES FOR SUBSCRIBED TOPICS")
        print("-" * 40)

        es = Elasticsearch(ES_CONN_STRING)

        for sub in subscriptions:
            topic_name = sub.topic.title

            # Count total articles with this topic in ES
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"language": user.learned_language.name}},
                            {"bool": {"should": [
                                {"match": {"topics": topic_name}},
                                {"match": {"topics_inferred": topic_name}}
                            ]}}
                        ]
                    }
                }
            }

            try:
                res = es.count(index=ES_ZINDEX, body=query)
                total = res.get('count', 0)
                print(f"   {topic_name}: {total} total articles in ES")
            except Exception as e:
                print(f"   {topic_name}: ES error - {e}")

    print()
    print("="*60)
    print("SUMMARY")
    print("="*60)

    issues = []
    if len(hidden_articles) > 50:
        issues.append(f"Many hidden articles ({len(hidden_articles)}) - could exhaust topic pool")
    if len(ignored_source_ids) > 20:
        issues.append(f"Many ignored sources ({len(ignored_source_ids)}) - could filter out topic-specific feeds")
    if not subscriptions:
        issues.append("No topic subscriptions - will see all topics by default")

    if issues:
        print("Potential issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("No obvious issues detected.")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m tools.diagnose_recommendations <user_email_or_id>")
        sys.exit(1)

    diagnose_user(sys.argv[1])
