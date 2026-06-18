#!/bin/bash
# Crawl script that runs a separate docker container for each language, one at a time.
# Languages are crawled sequentially to avoid pegging the shared Stanza service while
# the live API also needs it (My Articles, opening articles, etc.). Wrap the cron
# invocation with `flock -n /tmp/zeeguu-crawl.lock ...` so a slow run doesn't collide
# with the next scheduled one.
#
# Usage:
#   ./crawl_all_in_parallel.sh                           # Crawl default languages
#   ./crawl_all_in_parallel.sh da fr                     # Crawl only Danish and French
#   ./crawl_all_in_parallel.sh --provider anthropic da   # Crawl Danish with Anthropic
#   ./crawl_all_in_parallel.sh --provider deepseek       # Crawl defaults with Deepseek

API_DIR="/home/zeeguu/ops/running/api"
DOCKER_COMPOSE="docker compose -f $API_DIR/docker-compose.yml"

# Per-language hard-timeout ceiling, in minutes (enforced by run_crawler_bounded).
DEFAULT_MAX_TIME_MIN=25         # most languages
HIGH_VOLUME_MAX_TIME_MIN=50     # da/fr: more users + bigger backlogs, so a longer ceiling

# Per-language configuration: MAX_ARTICLES MAX_TIME_MINUTES
# Format: LANG_CONFIG_<code>="max_articles max_time_minutes"
# High activity languages (20+ active users in last 2 weeks)
LANG_CONFIG_da="100 $HIGH_VOLUME_MAX_TIME_MIN"  # 22 users - runs hourly
LANG_CONFIG_fr="40 $HIGH_VOLUME_MAX_TIME_MIN"   # 45 users - runs hourly
LANG_CONFIG_de="20 $DEFAULT_MAX_TIME_MIN"       # 31 users - runs hourly
LANG_CONFIG_en="20 $DEFAULT_MAX_TIME_MIN"       # 26 users

# Medium activity languages (10+ users)
LANG_CONFIG_nl="15 $DEFAULT_MAX_TIME_MIN"       # 10 users

# Low activity languages (1-3 users)
LANG_CONFIG_el="5 $DEFAULT_MAX_TIME_MIN"        # 3 users
LANG_CONFIG_pt="5 $DEFAULT_MAX_TIME_MIN"        # 1 user
LANG_CONFIG_ro="5 $DEFAULT_MAX_TIME_MIN"        # 1 user
LANG_CONFIG_es="5 $DEFAULT_MAX_TIME_MIN"        # 1 user
LANG_CONFIG_it="5 $DEFAULT_MAX_TIME_MIN"        # 1 user
LANG_CONFIG_sv="5 $DEFAULT_MAX_TIME_MIN"        # 0 users

# Default languages (when no language args provided)
# Note: da, fr, de run hourly via separate cron job
DEFAULT_LANGUAGES="pt sv ro nl en el es it"

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

# Use provided languages or defaults
if [[ -n "$LANG_ARGS" ]]; then
    LANGUAGES="$LANG_ARGS"
else
    LANGUAGES="$DEFAULT_LANGUAGES"
fi

# Generate timestamp for log files
TIMESTAMP=$(date +'%Y_%m_%d_%I_%M_%p')

# Status output disabled to avoid cron emails (logs go to $LOG_FILE)
# echo "=== Starting Parallel Crawl at $(date) ==="
# echo "Provider: $PROVIDER"
# echo "Languages: $LANGUAGES"
# echo ""

# Stop and remove any existing crawler containers
for lang in $LANGUAGES; do
    docker stop crawler_${lang} 2>/dev/null || true
    docker rm crawler_${lang} 2>/dev/null || true
done

# Run a single crawler container under a hard wall-clock ceiling, escalating how
# forcefully we take it down if it overruns:
#   1. SIGTERM at $hard_timeout_seconds — graceful: docker compose stops the
#      container and --rm removes it.
#   2. SIGKILL if it's STILL alive $GRACE_BEFORE_KILL later — for a crawl so wedged
#      it ignores SIGTERM.
#   3. `docker rm -f` to sweep up any container the kill orphaned, so it can't keep
#      holding /tmp/zeeguu-crawl.lock and stall every language's crawl (as happened
#      for 3 days in June 2026).
# This is only a backstop — the per-article SIGALRM watchdog in article_downloader.py
# is the primary guard and keeps healthy crawls flowing.
GRACE_BEFORE_KILL="60s"

run_crawler_bounded() {
    local lang="$1"
    local hard_timeout_seconds="$2"
    local log_file="$3"
    shift 3   # remaining args = the python crawl command line

    timeout --kill-after="$GRACE_BEFORE_KILL" "$hard_timeout_seconds" \
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

# Run one crawler container at a time, in the order languages were given.
# Sequential by design — parallel crawls saturate Stanza and slow the live API.
for lang in $LANGUAGES; do
    # Get per-language config
    config_var="LANG_CONFIG_${lang}"
    config="${!config_var}"

    if [[ -z "$config" ]]; then
        echo "Warning: No config for language '$lang', skipping"
        continue
    fi

    max_articles=$(echo $config | cut -d' ' -f1)
    max_time_minutes=$(echo $config | cut -d' ' -f2)
    max_time_seconds=$((max_time_minutes * 60))

    LOG_FILE="/var/log/zeeguu/crawler/crawler-${lang}-${TIMESTAMP}.log"

    run_crawler_bounded "$lang" "$max_time_seconds" "$LOG_FILE" \
        zeeguu/operations/crawler/crawl.py "$lang" --provider "$PROVIDER" --max-articles "$max_articles" --max-time "$max_time_seconds"
done

# echo ""
# echo "=== Parallel Crawl completed at $(date) ==="
