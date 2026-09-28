#!/bin/bash
set -e

echo "=== Zeeguu API Startup ==="

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
