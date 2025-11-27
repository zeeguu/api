#!/bin/bash
# Crawl script that runs a separate docker container for each language in parallel

cd /home/zeeguu/ops/running/api

# Per-language configuration: MAX_ARTICLES MAX_TIME_MINUTES
# Format: LANG_CONFIG_<code>="max_articles max_time_minutes"
LANG_CONFIG_da="1000 5"
LANG_CONFIG_pt="1000 5"
LANG_CONFIG_sv="1000 5"
LANG_CONFIG_ro="1000 5"
LANG_CONFIG_nl="1000 5"
LANG_CONFIG_fr="1000 5"
LANG_CONFIG_en="1000 5"
LANG_CONFIG_el="1000 5"
LANG_CONFIG_de="1000 5"
LANG_CONFIG_es="1000 5"
LANG_CONFIG_it="1000 5"

# All supported languages
LANGUAGES="da pt sv ro nl fr en el de es it"

# Default provider
PROVIDER="deepseek"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --provider)
            PROVIDER="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Generate timestamp for log files
TIMESTAMP=$(date +'%Y_%m_%d_%I_%M_%p')

echo "=== Starting Parallel Crawl at $(date) ==="
echo "Provider: $PROVIDER"
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
    max_articles=$(echo $config | cut -d' ' -f1)
    max_time_minutes=$(echo $config | cut -d' ' -f2)
    max_time_seconds=$((max_time_minutes * 60))

    LOG_FILE="/var/log/zeeguu/crawler/crawler-${lang}-${TIMESTAMP}.log"
    echo "Starting crawler for $lang (max_articles=$max_articles, max_time=${max_time_minutes}min) -> $LOG_FILE"
    docker compose run --rm --name crawler_${lang} crawler python zeeguu/operations/crawler/crawl.py $lang --provider $PROVIDER --max-articles $max_articles --max-time $max_time_seconds >> "$LOG_FILE" 2>&1 &
done

# Wait for all to complete
wait

echo ""
echo "=== Parallel Crawl completed at $(date) ==="
