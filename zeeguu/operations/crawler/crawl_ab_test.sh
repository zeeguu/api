#!/bin/bash
# Crawl script for A/B testing DeepSeek vs Anthropic
# Splits languages in half and runs both providers in parallel

# All languages in priority order
ALL_LANGUAGES="da pt sv ro nl fr en el de es it"

# Split into two groups (roughly equal)
DEEPSEEK_LANGS="da pt sv ro nl"
ANTHROPIC_LANGS="fr en el de es it"

# API directory should be the current working directory when script is run
# This allows running from /home/zeeguu/ops/running/api on the server
API_DIR="${API_DIR:-$(pwd)}"

# Parse arguments (pass through to crawler)
EXTRA_ARGS="$@"

# Ensure log directory exists
LOG_DIR="/var/log/zeeguu/crawler"
mkdir -p "$LOG_DIR"

# Generate log filename with timestamp
LOG_FILE="$LOG_DIR/crawler-$(date +'%Y_%m_%d_%I_%M_%p').log"

echo "=== Starting A/B Test Crawl at $(date) ===" | tee -a "$LOG_FILE"
echo "DeepSeek languages: $DEEPSEEK_LANGS" | tee -a "$LOG_FILE"
echo "Anthropic languages: $ANTHROPIC_LANGS" | tee -a "$LOG_FILE"
echo "Extra arguments: $EXTRA_ARGS" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Run both in parallel in background
cd "$API_DIR"

# DeepSeek crawler
(
  echo ">>> Starting DeepSeek crawler at $(date)" >> "$LOG_FILE"
  docker compose rm -f crawler_w_deepseek 2>/dev/null || true
  docker compose run --rm --name crawler_w_deepseek crawler \
    python zeeguu/operations/crawler/crawl.py $DEEPSEEK_LANGS --provider deepseek $EXTRA_ARGS \
    >> "$LOG_FILE" 2>&1
  echo ">>> DeepSeek crawler finished at $(date)" >> "$LOG_FILE"
) &
DEEPSEEK_PID=$!

# Anthropic crawler
(
  echo ">>> Starting Anthropic crawler at $(date)" >> "$LOG_FILE"
  docker compose rm -f crawler_w_anthropic 2>/dev/null || true
  docker compose run --rm --name crawler_w_anthropic crawler \
    python zeeguu/operations/crawler/crawl.py $ANTHROPIC_LANGS --provider anthropic $EXTRA_ARGS \
    >> "$LOG_FILE" 2>&1
  echo ">>> Anthropic crawler finished at $(date)" >> "$LOG_FILE"
) &
ANTHROPIC_PID=$!

# Wait for both to complete
wait $DEEPSEEK_PID
DEEPSEEK_EXIT=$?

wait $ANTHROPIC_PID
ANTHROPIC_EXIT=$?

# Report results
echo "" | tee -a "$LOG_FILE"
echo "=== A/B Test Crawl completed at $(date) ===" | tee -a "$LOG_FILE"
echo "DeepSeek exit code: $DEEPSEEK_EXIT" | tee -a "$LOG_FILE"
echo "Anthropic exit code: $ANTHROPIC_EXIT" | tee -a "$LOG_FILE"

# Exit with error if either failed
if [ $DEEPSEEK_EXIT -ne 0 ] || [ $ANTHROPIC_EXIT -ne 0 ]; then
  exit 1
fi

exit 0
