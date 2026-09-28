#!/bin/bash
set -e

echo "=== Zeeguu API Startup ==="

# newspaper3k creates these at import time with an unguarded exists-then-mkdir
# (newspaper/settings.py). Workers import it concurrently on a fresh container,
# so one can hit FileExistsError, fail to boot, and take the whole container down.
mkdir -p /tmp/.newspaper_scraper/memoized /tmp/.newspaper_scraper/feed_category_cache

echo "Starting Gunicorn..."
exec gunicorn \
    --bind 0.0.0.0:8080 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --threads 15 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "zeeguu.api.app:create_app()"
