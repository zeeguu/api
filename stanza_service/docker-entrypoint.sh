#!/bin/bash
set -e

echo "=== Stanza Service Startup ==="

# Ensure Stanza models are downloaded
echo "Checking Stanza models..."
python install_models.py

echo "Starting Gunicorn with preload_app (models loaded in master process)..."
exec gunicorn --config gunicorn.conf.py app:app
