#!/usr/bin/env python
"""
Crawl articles for one or more languages sequentially.

Usage:
    python tools/crawler/crawl.py                        # Crawl all languages (default)
    python tools/crawler/crawl.py --all                  # Crawl all languages (explicit)
    python tools/crawler/crawl.py da                     # Crawl only Danish
    python tools/crawler/crawl.py da pt en               # Crawl Danish, Portuguese, and English
    python tools/crawler/crawl.py --max-time 600 da      # Set max 10 minutes per feed

Options:
    --max-time SECONDS   Maximum time in seconds to spend per feed (default: 300)
"""
from datetime import datetime
import sys
import argparse

from feed_retrieval import retrieve_articles_for_language
from zeeguu.logging import log
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model import Feed
import logging

# Configure logging to show INFO level
logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
logging.getLogger("zeeguu.core").setLevel(logging.INFO)
logging.getLogger("zeeguu.logging").setLevel(logging.INFO)

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()


def generate_crawl_summary(crawl_reports):
    """Generate a concise summary from multiple crawl reports"""
    summary = "ZEEGUU CRAWLER SUMMARY\n"
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
        summary += f" | Time: {lang_data.get('total_time', 0):.1f}s\n"

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


# All available languages in order of priority
ALL_LANGUAGES = ['da', 'pt', 'sv', 'ro', 'nl', 'fr', 'en', 'el', 'de', 'es', 'it']

# Parse command line arguments
parser = argparse.ArgumentParser(description='Crawl articles for one or more languages')
parser.add_argument('languages', nargs='*', help='Language codes to crawl (default: all)')
parser.add_argument('--all', action='store_true', help='Crawl all languages')
parser.add_argument('--max-time', type=int, default=300,
                   help='Maximum time in seconds per feed (default: 300)')

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
log(f"=== Starting crawl for languages: {languages_to_crawl} at: {start} ===")
log(f"=== Max time per feed: {args.max_time}s ===")

crawl_reports = {}

for lang in languages_to_crawl:
    lang_start = datetime.now()
    log(f"\n>>> Starting {lang.upper()} crawler <<<")
    try:
        crawl_report = retrieve_articles_for_language(lang, send_email=False)
        crawl_reports[lang] = crawl_report
        lang_duration = datetime.now() - lang_start
        log(f">>> Finished {lang.upper()} in {lang_duration} <<<")
    except Exception as e:
        log(f">>> ERROR in {lang.upper()}: {e} <<<")
        import traceback
        traceback.print_exc()

end = datetime.now()
total_duration = end - start
log(f"=== Finished crawling {len(languages_to_crawl)} language(s) at: {end} ===")
log(f"=== Total duration: {total_duration} ===")

# Generate and send summary email
summary = generate_crawl_summary(crawl_reports)
log("\n" + summary)

try:
    mailer = ZeeguuMailer(
        f"Zeeguu Crawler Summary - {end.strftime('%Y-%m-%d %H:%M')}",
        summary,
        "zeeguu.team@gmail.com",
    )
    mailer.send()
    log("Summary email sent successfully")
except Exception as e:
    log(f"Failed to send summary email: {e}")
