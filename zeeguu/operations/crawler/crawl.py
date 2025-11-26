#!/usr/bin/env python
"""
Round-robin crawler that interleaves feeds across multiple languages.

This prevents one language from blocking progress in others when encountering
slow feeds or timeouts. Processes feeds in a fair rotation: one feed from each
language, then repeat.

Usage:
    python tools/crawler/crawl_roundrobin.py                    # Crawl all languages
    python tools/crawler/crawl_roundrobin.py --all              # Crawl all languages (explicit)
    python tools/crawler/crawl_roundrobin.py da pt en           # Crawl specific languages
    python tools/crawler/crawl_roundrobin.py --max-time 600 da  # Set max 10 minutes per feed
    python tools/crawler/crawl_roundrobin.py --recent-days 2    # Only articles from last 2 days
    python tools/crawler/crawl_roundrobin.py --max-articles 50  # Process max 50 articles per feed

Options:
    --max-time SECONDS     Maximum time in seconds to spend per feed (default: 300)
    --articles-per-feed N  Max articles to process per feed before moving to next (default: 1)
    --recent-days N        Only process articles from last N days (overrides feed last_crawled_time)
    --max-articles N       Maximum articles to download per feed (default: 1000)
"""
from datetime import datetime, timedelta
import sys
import argparse
from collections import defaultdict
import traceback

from sqlalchemy.exc import PendingRollbackError
from time import time

import zeeguu.core
from zeeguu.logging import log
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.content_retriever.article_downloader import download_from_feed
from zeeguu.core.model import Feed, Language
from zeeguu.operations.crawler.crawl_report import CrawlReport
import logging

# Configure logging to show INFO level
logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
logging.getLogger("zeeguu.core").setLevel(logging.INFO)
logging.getLogger("zeeguu.logging").setLevel(logging.INFO)

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session


def generate_crawl_summary(crawl_reports):
    """Generate a concise summary from multiple crawl reports"""
    summary = "ZEEGUU CRAWLER SUMMARY (Round-Robin)\n"
    summary += "=" * 60 + "\n\n"

    total_new = 0
    total_in_db = 0
    total_low_quality = 0
    total_errors = 0

    for lang_code, report in crawl_reports.items():
        lang_data = report.data["lang"][lang_code]
        lang_new = 0
        lang_in_db = 0
        lang_low_quality = 0
        lang_errors = 0

        summary += f"\n{lang_code.upper()}\n"
        summary += "-" * 40 + "\n"

        for feed_id, feed_data in lang_data["feeds"].items():
            feed = Feed.find_by_id(feed_id)
            if not feed:
                continue

            new = feed_data.get("total_downloaded", 0) or 0
            in_db = feed_data.get("total_in_db", 0) or 0
            low_q = feed_data.get("total_low_quality", 0) or 0
            errors = len(feed_data.get("feed_errors", []))

            lang_new += new
            lang_in_db += in_db
            lang_low_quality += low_q
            lang_errors += errors

            # Only show feeds with activity or errors
            if new > 0 or errors > 0:
                status = ""
                if errors > 0:
                    status = f" [ERROR]"
                elif new == 0 and in_db > 0:
                    status = " [all in DB]"

                feed_time = feed_data.get("crawl_time", 0) or 0
                # Mark feeds that hit the 5-minute limit
                if feed_time >= 300:
                    status += " [MAX_TIME_REACHED]"

                summary += f"  {feed.title[:40]:40s} | New: {new:3d} | InDB: {in_db:3d} | LowQ: {low_q:3d} | Time: {feed_time:5.1f}s{status}\n"

        total_new += lang_new
        total_in_db += lang_in_db
        total_low_quality += lang_low_quality
        total_errors += lang_errors

        summary += f"\n  {lang_code.upper()} Total: {lang_new} new, {lang_in_db} already in DB, {lang_low_quality} low quality"
        if lang_errors > 0:
            summary += f", {lang_errors} errors"
        summary += f" | Time: {lang_data.get('total_time', 0) or 0:.1f}s\n"

    # Calculate total time
    total_time = sum(
        report.data["lang"][lang_code].get("total_time", 0) or 0
        for lang_code, report in crawl_reports.items()
    )

    summary += "\n" + "=" * 60 + "\n"
    summary += f"OVERALL: {total_new} new articles, {total_in_db} already in DB, {total_low_quality} low quality"
    if total_errors > 0:
        summary += f", {total_errors} errors"
    summary += f"\nTotal crawl duration: {total_time:.1f}s ({total_time/60:.1f} minutes)"
    summary += "\n"

    return summary


def crawl_round_robin(languages_to_crawl, articles_per_feed=1, recent_days=None, max_articles_per_feed=1000, simplification_provider='deepseek'):
    """
    Crawl feeds in round-robin fashion across languages.

    Args:
        languages_to_crawl: List of language codes to crawl
        articles_per_feed: Number of articles to process per feed before switching (default: 1)
        recent_days: Only process articles from last N days (overrides feed last_crawled_time)
        max_articles_per_feed: Maximum articles to download per feed (default: 1000)
        simplification_provider: LLM provider for article simplification (default: 'deepseek')

    Returns:
        Dict of crawl reports per language
    """
    # Initialize crawl reports for each language
    crawl_reports = {}
    for lang_code in languages_to_crawl:
        crawl_report = CrawlReport()
        crawl_report.add_language(lang_code)
        crawl_reports[lang_code] = crawl_report

    # Get all feeds grouped by language
    feeds_by_language = {}
    total_feeds = 0

    for lang_code in languages_to_crawl:
        language = Language.find(lang_code)
        feeds = Feed.query.filter_by(language_id=language.id).filter_by(deactivated=False).all()
        feeds_by_language[lang_code] = feeds
        total_feeds += len(feeds)
        log(f"{lang_code.upper()}: {len(feeds)} feeds")

    log(f"\nTotal feeds across all languages: {total_feeds}")
    log(f"Processing {articles_per_feed} article(s) per feed before switching")

    # If recent_days is set, temporarily override last_crawled_time for all feeds
    if recent_days:
        min_date = datetime.now() - timedelta(days=recent_days)
        log(f"*** Filtering articles: Only processing from last {recent_days} days (since {min_date.strftime('%Y-%m-%d %H:%M')})")
        for lang_code in languages_to_crawl:
            for feed in feeds_by_language[lang_code]:
                if feed.last_crawled_time and feed.last_crawled_time < min_date:
                    log(f"    Overriding {feed.title}: {feed.last_crawled_time} -> {min_date}")
                    feed.last_crawled_time = min_date
    log("")

    # Track which feed index we're at for each language
    feed_indices = {lang: 0 for lang in languages_to_crawl}
    feeds_completed = 0

    # Round-robin through languages until all feeds are processed
    while feeds_completed < total_feeds:
        made_progress = False

        for lang_code in languages_to_crawl:
            feeds = feeds_by_language[lang_code]
            idx = feed_indices[lang_code]

            # Skip if this language has no more feeds
            if idx >= len(feeds):
                continue

            made_progress = True
            feed = feeds[idx]
            crawl_report = crawl_reports[lang_code]

            # Add feed to report
            crawl_report.add_feed(feed)

            if feed.deactivated:
                feed_indices[lang_code] += 1
                feeds_completed += 1
                continue

            # Process this feed
            try:
                log("")
                log(f"[{lang_code.upper()}] >>>>> {feed.title} ({idx+1}/{len(feeds)}) <<<<<")

                feed_start_time = time()

                # Download from feed (this already handles article limits internally)
                download_from_feed(
                    feed,
                    db_session,
                    crawl_report,
                    limit=max_articles_per_feed,
                    simplification_provider=simplification_provider,
                )

                feed_time = time() - feed_start_time
                log(f"*** Feed processing time: {feed_time:.1f}s")

            except PendingRollbackError as e:
                db_session.rollback()
                log("Rollback required; full stack trace:")
                traceback.print_exc()
                crawl_report.add_feed_error(feed, str(e))

            except Exception as e:
                traceback.print_exc()
                crawl_report.add_feed_error(feed, str(e))

            # Move to next feed for this language
            feed_indices[lang_code] += 1
            feeds_completed += 1

            log(f"*** Progress: {feeds_completed}/{total_feeds} feeds completed ({feeds_completed*100//total_feeds}%)")

        # If no language made progress, all feeds are done
        if not made_progress:
            break

    log(f"\nFinished processing {feeds_completed} feeds across {len(languages_to_crawl)} languages")

    # Calculate and save total times per language
    for lang_code, crawl_report in crawl_reports.items():
        # Calculate total time for this language
        lang_data = crawl_report.data["lang"][lang_code]
        total_time = sum(
            feed_data.get("crawl_time", 0) or 0
            for feed_data in lang_data["feeds"].values()
        )
        crawl_report.set_total_time(lang_code, total_time)
        crawl_report.save_crawl_report()

    return crawl_reports


# All available languages in order of priority
ALL_LANGUAGES = ['da', 'pt', 'sv', 'ro', 'nl', 'fr', 'en', 'el', 'de', 'es', 'it']

# Parse command line arguments
parser = argparse.ArgumentParser(description='Crawl articles in round-robin fashion across languages')
parser.add_argument('languages', nargs='*', help='Language codes to crawl (default: all)')
parser.add_argument('--all', action='store_true', help='Crawl all languages')
parser.add_argument('--max-time', type=int, default=300,
                   help='Maximum time in seconds per feed (default: 300)')
parser.add_argument('--articles-per-feed', type=int, default=1,
                   help='Number of articles to process per feed before switching (default: 1)')
parser.add_argument('--recent-days', type=int, default=None,
                   help='Only process articles from last N days (overrides feed last_crawled_time)')
parser.add_argument('--max-articles', type=int, default=1000,
                   help='Maximum articles to download per feed (default: 1000)')
parser.add_argument('--provider', type=str, choices=['deepseek', 'anthropic'], default='deepseek',
                   help='LLM provider for article simplification (default: deepseek)')

args = parser.parse_args()

# Set the max feed processing time as environment variable for the downloader to use
import os
os.environ['MAX_FEED_PROCESSING_TIME_SECONDS'] = str(args.max_time)

# Determine which languages to crawl
if args.all or not args.languages:
    languages_to_crawl = ALL_LANGUAGES
else:
    languages_to_crawl = args.languages
    # Validate languages
    invalid = [lang for lang in languages_to_crawl if lang not in ALL_LANGUAGES]
    if invalid:
        log(f"ERROR: Invalid language codes: {invalid}")
        log(f"Valid languages: {ALL_LANGUAGES}")
        sys.exit(1)

start = datetime.now()
log(f"=== Starting crawl for languages: {languages_to_crawl} ===")
log(f"=== Started at: {start} ===")
log(f"=== Max time per feed: {args.max_time}s ===")
log(f"=== Max articles per feed: {args.max_articles} ===")
log(f"=== Articles per feed (round-robin): {args.articles_per_feed} ===")
log(f"=== Simplification provider: {args.provider.upper()} ===")
if args.recent_days:
    log(f"=== Recent days filter: {args.recent_days} days ===")
log("")

try:
    crawl_reports = crawl_round_robin(languages_to_crawl, args.articles_per_feed, args.recent_days, args.max_articles, args.provider)

    end = datetime.now()
    total_duration = end - start
    log(f"\n=== Finished at: {end} ===")
    log(f"=== Total duration: {total_duration} ===")

    # Generate and send summary email
    summary = generate_crawl_summary(crawl_reports)
    log("\n" + summary)

    try:
        mailer = ZeeguuMailer(
            f"Zeeguu Round-Robin Crawler Summary - {end.strftime('%Y-%m-%d %H:%M')}",
            summary,
            "zeeguu.team@gmail.com",
        )
        mailer.send()
        log("Summary email sent successfully")
    except Exception as e:
        log(f"Failed to send summary email: {e}")

except Exception as e:
    log(f"FATAL ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
