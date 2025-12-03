#!/bin/bash
# Crawl script for testing two Anthropic crawlers in parallel
# Splits languages across two instances to test parallel throughput

cd /home/zeeguu/ops/running/api

# Generate log filenames with timestamp
TIMESTAMP=$(date +'%Y_%m_%d_%I_%M_%p')
LOG_FILE_ANTHROPIC_1="/var/log/zeeguu/crawler/crawler-anthropic-1-${TIMESTAMP}.log"
LOG_FILE_ANTHROPIC_2="/var/log/zeeguu/crawler/crawler-anthropic-2-${TIMESTAMP}.log"

# Max articles per feed
MAX_ARTICLES=10

echo "=== Starting Dual Anthropic Crawl at $(date) ==="
echo "Anthropic #1 log: $LOG_FILE_ANTHROPIC_1 (languages: da pt sv ro nl)"
echo "Anthropic #2 log: $LOG_FILE_ANTHROPIC_2 (languages: fr en el de es it)"
echo "Max articles per feed: $MAX_ARTICLES"

# Stop and remove specific crawler containers if they exist
docker stop crawler_anthropic_1 2>/dev/null || true
docker rm crawler_anthropic_1 2>/dev/null || true
docker stop crawler_anthropic_2 2>/dev/null || true
docker rm crawler_anthropic_2 2>/dev/null || true

# Run both Anthropic crawlers in parallel with different language sets
docker compose run --rm --name crawler_anthropic_1 run_task python zeeguu/operations/crawler/crawl.py da pt sv ro nl --provider anthropic --max-articles $MAX_ARTICLES "$@" >> "$LOG_FILE_ANTHROPIC_1" 2>&1 &
docker compose run --rm --name crawler_anthropic_2 run_task python zeeguu/operations/crawler/crawl.py fr en el de es it --provider anthropic --max-articles $MAX_ARTICLES "$@" >> "$LOG_FILE_ANTHROPIC_2" 2>&1 &

# Wait for both to complete
wait

echo "=== Dual Anthropic Crawl completed at $(date) ==="
