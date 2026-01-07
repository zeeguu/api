#!/bin/bash
set -e

echo "=== Stanza Service Startup ==="

# Ensure Stanza models are downloaded (files only, not loaded into memory)
echo "Checking Stanza models..."
python install_models.py

echo "Starting Gunicorn (models load lazily on first request per language)..."
exec gunicorn --config gunicorn.conf.py app:app
