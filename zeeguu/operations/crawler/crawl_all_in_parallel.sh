#!/bin/bash
# Crawl script that runs a separate docker container for each language, one at a time.
# Languages are crawled sequentially to avoid pegging the shared Stanza service while
# the live API also needs it (My Articles, opening articles, etc.). Wrap the cron
# invocation with `flock -n /tmp/zeeguu-crawl.lock ...` so a slow run doesn't collide
# with the next scheduled one.
#
# Which languages run when, and with what limits, lives in zeeguu/core/crawl_schedule.py.
# Cron calls this once an hour with no language args; the schedule decides what's due.
#
# Usage:
#   ./crawl_all_in_parallel.sh                           # Crawl the languages due this hour
#   ./crawl_all_in_parallel.sh da fr                     # Crawl only Danish and French, now
#   ./crawl_all_in_parallel.sh --provider anthropic da   # Crawl Danish with Anthropic
#   ./crawl_all_in_parallel.sh --provider deepseek       # Crawl what's due with Deepseek

API_DIR="/home/zeeguu/ops/running/api"
DOCKER_COMPOSE="docker compose -f $API_DIR/docker-compose.yml"

SCHEDULE="$(dirname "$0")/../../core/crawl_schedule.py"

# Default provider
PROVIDER="deepseek"

# Collect language arguments
LANG_ARGS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        *)
            # Assume it's a language code
            LANG_ARGS="$LANG_ARGS $1"
            shift
            ;;
    esac
done

# One "code max_articles max_minutes" line per language to crawl, in order.
# Runs with the host python3 (stdlib only), so "due this hour" uses cron's clock.
if ! PLAN=$(python3 "$SCHEDULE" $LANG_ARGS); then
    exit 1
fi

# Generate timestamp for log files
TIMESTAMP=$(date +'%Y_%m_%d_%I_%M_%p')

# Status output disabled to avoid cron emails (logs go to $LOG_FILE)
# echo "=== Starting Parallel Crawl at $(date) ==="
# echo "Provider: $PROVIDER"
# echo "Plan: $PLAN"
# echo ""

# Stop and remove any existing crawler containers
while read -r lang _; do
    [[ -z "$lang" ]] && continue
    docker stop crawler_${lang} 2>/dev/null || true
    docker rm crawler_${lang} 2>/dev/null || true
done <<< "$PLAN"

# Run one crawler container under a hard wall-clock ceiling, escalating how
# forcefully we take it down if it overruns:
#   1. SIGTERM at $hard_timeout_seconds — graceful: docker compose stops the
#      container and --rm removes it.
#   2. SIGKILL if it's STILL alive $KILL_GRACE later — for a crawl so wedged it
#      ignores SIGTERM.
#   3. `docker rm -f` to sweep up any container the kill orphaned, so it can't keep
#      holding /tmp/zeeguu-crawl.lock and stall every language's crawl (as happened
#      for 3 days in June 2026).
# This is only a backstop — the per-article SIGALRM watchdog in article_downloader.py
# is the primary guard and keeps healthy crawls flowing.
KILL_GRACE="60s"

run_crawler_with_hard_timeout() {
    local lang="$1"
    local hard_timeout_seconds="$2"
    local log_file="$3"
    shift 3   # remaining args = the python crawl command line

    timeout --kill-after="$KILL_GRACE" "$hard_timeout_seconds" \
        $DOCKER_COMPOSE run --rm --name "crawler_${lang}" run_task python "$@" \
        >> "$log_file" 2>&1
    local rc=$?

    # timeout exits 124 (had to SIGTERM) or 137 (had to SIGKILL) when it tripped.
    if [[ $rc -eq 124 || $rc -eq 137 ]]; then
        echo "[$(date)] crawler_${lang} exceeded ${hard_timeout_seconds}s — force-removing container to release the crawl lock" >> "$log_file"
        docker rm -f "crawler_${lang}" >/dev/null 2>&1 || true
    fi
    return $rc
}

# Run one crawler container at a time, in schedule order.
# Sequential by design — parallel crawls saturate Stanza and slow the live API.
while read -r lang max_articles max_time_minutes; do
    [[ -z "$lang" ]] && continue
    max_time_seconds=$((max_time_minutes * 60))

    LOG_FILE="/var/log/zeeguu/crawler/crawler-${lang}-${TIMESTAMP}.log"

    # </dev/null: docker compose run would otherwise read the rest of $PLAN from stdin
    run_crawler_with_hard_timeout "$lang" "$max_time_seconds" "$LOG_FILE" \
        zeeguu/operations/crawler/crawl.py "$lang" --provider "$PROVIDER" --max-articles "$max_articles" --max-time "$max_time_seconds" \
        </dev/null
done <<< "$PLAN"
