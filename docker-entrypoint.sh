#!/bin/bash
set -e

echo "=== Zeeguu API Startup ==="

# Ensure Stanza models are downloaded
echo "Checking Stanza models..."
python install_stanza_models.py

echo "Starting Gunicorn..."
exec gunicorn \
    --bind 0.0.0.0:8080 \
    --workers 4 \
    --threads 15 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "zeeguu.api.app:create_app()"
