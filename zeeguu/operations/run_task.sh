#!/bin/bash
# Wrapper script for running docker compose tasks
#
# Usage:
#   ./run_task.sh <task_name> <python_script> [args...]
#
# Example:
#   ./run_task.sh report_generator tools/report_generator/generate_report.py
#   ./run_task.sh email_sender tools/send_subscription_emails.py

API_DIR="/home/zeeguu/ops/running/api"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <task_name> <python_script> [args...]"
    exit 1
fi

TASK_NAME="$1"
shift

docker compose -f "$API_DIR/docker-compose.yml" run --rm --name "$TASK_NAME" zapi python "$@"
