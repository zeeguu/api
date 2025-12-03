#!/bin/bash
# Wrapper script for running docker compose tasks with automatic logging
#
# Usage:
#   ./run_task.sh <task_name> <python_script> [args...]
#
# Example:
#   ./run_task.sh report_generator tools/report_generator/generate_report.py
#   ./run_task.sh email_sender tools/send_subscription_emails.py
#
# Logs are written to: /var/log/zeeguu/<task_name>-<date>.log

API_DIR="/home/zeeguu/ops/running/api"
LOG_DIR="/var/log/zeeguu"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <task_name> <python_script> [args...]"
    exit 1
fi

TASK_NAME="$1"
shift

TIMESTAMP=$(date +'%Y_%m_%d_%H_%M')
LOG_FILE="$LOG_DIR/${TASK_NAME}-${TIMESTAMP}.log"

# Cleanup any stuck container with the same name before starting
# This prevents "container name already in use" errors from stuck tasks
if docker ps -a --format '{{.Names}}' | grep -q "^${TASK_NAME}$"; then
    echo "[$(date)] WARNING: Found existing container '$TASK_NAME' - stopping and removing it" >> "$LOG_FILE"
    docker stop "$TASK_NAME" 2>/dev/null || true
    docker rm "$TASK_NAME" 2>/dev/null || true
fi

docker compose -f "$API_DIR/docker-compose.yml" run --rm --name "$TASK_NAME" zapi python "$@" >> "$LOG_FILE" 2>&1
