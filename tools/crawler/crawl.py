#!/usr/bin/env python
"""
Crawl articles for one or more languages sequentially.

Usage:
    python tools/crawler/crawl.py                # Crawl all languages (default)
    python tools/crawler/crawl.py --all          # Crawl all languages (explicit)
    python tools/crawler/crawl.py da             # Crawl only Danish
    python tools/crawler/crawl.py da pt en       # Crawl Danish, Portuguese, and English
"""
from datetime import datetime
import sys

from feed_retrieval import retrieve_articles_for_language
from zeeguu.logging import log
import logging

# Configure logging to show INFO level
logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
logging.getLogger("zeeguu.core").setLevel(logging.INFO)
logging.getLogger("zeeguu.logging").setLevel(logging.INFO)

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

# All available languages in order of priority
ALL_LANGUAGES = ['da', 'pt', 'sv', 'ro', 'nl', 'fr', 'en', 'el', 'de', 'es', 'it']

# Get languages from command line args, or use all if none specified
if len(sys.argv) > 1 and sys.argv[1] != '--all':
    languages_to_crawl = sys.argv[1:]
    # Validate languages
    invalid = [lang for lang in languages_to_crawl if lang not in ALL_LANGUAGES]
    if invalid:
        log(f"ERROR: Invalid language codes: {invalid}")
        log(f"Valid languages: {ALL_LANGUAGES}")
        sys.exit(1)
else:
    languages_to_crawl = ALL_LANGUAGES

start = datetime.now()
log(f"=== Starting crawl for languages: {languages_to_crawl} at: {start} ===")

for lang in languages_to_crawl:
    lang_start = datetime.now()
    log(f"\n>>> Starting {lang.upper()} crawler <<<")
    try:
        retrieve_articles_for_language(lang, send_email=False)
        lang_duration = datetime.now() - lang_start
        log(f">>> Finished {lang.upper()} in {lang_duration} <<<")
    except Exception as e:
        log(f">>> ERROR in {lang.upper()}: {e} <<<")
        import traceback
        traceback.print_exc()

end = datetime.now()
log(f"=== Finished crawling {len(languages_to_crawl)} language(s) at: {end} ===")
log(f"=== Total duration: {end - start} ===")
