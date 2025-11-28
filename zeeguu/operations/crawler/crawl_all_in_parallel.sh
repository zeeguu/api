#!/bin/bash
# Crawl script that runs a separate docker container for each language in parallel
#
# Usage:
#   ./crawl_all_in_parallel.sh                           # Crawl default languages
#   ./crawl_all_in_parallel.sh da fr                     # Crawl only Danish and French
#   ./crawl_all_in_parallel.sh --provider anthropic da   # Crawl Danish with Anthropic
#   ./crawl_all_in_parallel.sh --provider deepseek       # Crawl defaults with Deepseek

API_DIR="/home/zeeguu/ops/running/api"
DOCKER_COMPOSE="docker compose -f $API_DIR/docker-compose.yml"

# Per-language configuration: MAX_ARTICLES MAX_TIME_MINUTES
# Format: LANG_CONFIG_<code>="max_articles max_time_minutes"
# High activity languages (20+ active users in last 2 weeks)
LANG_CONFIG_da="100 50"  # 22 users - runs hourly
LANG_CONFIG_fr="40 50"   # 45 users - runs hourly
LANG_CONFIG_de="20 25"   # 31 users - runs hourly
LANG_CONFIG_en="20 25"   # 26 users

# Medium activity languages (10+ users)
LANG_CONFIG_nl="15 25"   # 10 users

# Low activity languages (1-3 users)
LANG_CONFIG_el="5 25"    # 3 users
LANG_CONFIG_pt="5 25"    # 1 user
LANG_CONFIG_ro="5 25"    # 1 user
LANG_CONFIG_es="5 25"    # 1 user
LANG_CONFIG_it="5 25"    # 1 user
LANG_CONFIG_sv="5 25"    # 0 users

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

echo "=== Starting Parallel Crawl at $(date) ==="
echo "Provider: $PROVIDER"
echo "Languages: $LANGUAGES"
echo ""

# Stop and remove any existing crawler containers
for lang in $LANGUAGES; do
    docker stop crawler_${lang} 2>/dev/null || true
    docker rm crawler_${lang} 2>/dev/null || true
done

# Start a crawler container for each language
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
    echo "Starting crawler for $lang (max_articles=$max_articles, max_time=${max_time_minutes}min) -> $LOG_FILE"
    $DOCKER_COMPOSE run --rm --name crawler_${lang} crawler python zeeguu/operations/crawler/crawl.py $lang --provider $PROVIDER --max-articles $max_articles --max-time $max_time_seconds >> "$LOG_FILE" 2>&1 &
done

# Wait for all to complete
wait

echo ""
echo "=== Parallel Crawl completed at $(date) ==="
