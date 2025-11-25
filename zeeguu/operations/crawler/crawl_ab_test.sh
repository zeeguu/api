#!/bin/bash
# Crawl script for A/B testing DeepSeek vs Anthropic
# Run both providers in parallel with separate log files

cd /home/zeeguu/ops/running/api

# Generate log filenames with timestamp
TIMESTAMP=$(date +'%Y_%m_%d_%I_%M_%p')
LOG_FILE_DEEPSEEK="/var/log/zeeguu/crawler/crawler-deepseek-${TIMESTAMP}.log"
LOG_FILE_ANTHROPIC="/var/log/zeeguu/crawler/crawler-anthropic-${TIMESTAMP}.log"

# Limits for each provider (can be adjusted)
DEEPSEEK_MAX_ARTICLES=5
ANTHROPIC_MAX_ARTICLES=5

echo "=== Starting A/B Test Crawl at $(date) ==="
echo "DeepSeek log: $LOG_FILE_DEEPSEEK (max articles: $DEEPSEEK_MAX_ARTICLES)"
echo "Anthropic log: $LOG_FILE_ANTHROPIC (max articles: $ANTHROPIC_MAX_ARTICLES)"

# Run both crawlers in parallel
docker compose run --rm crawler python zeeguu/operations/crawler/crawl.py da pt sv ro nl --provider deepseek --max-articles $DEEPSEEK_MAX_ARTICLES "$@" >> "$LOG_FILE_DEEPSEEK" 2>&1 &
docker compose run --rm crawler python zeeguu/operations/crawler/crawl.py fr en el de es it --provider anthropic --max-articles $ANTHROPIC_MAX_ARTICLES "$@" >> "$LOG_FILE_ANTHROPIC" 2>&1 &

# Wait for both to complete
wait

echo "=== A/B Test Crawl completed at $(date) ==="
