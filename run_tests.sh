#!/bin/sh
# Smart test runner using pytest-testmon
# Only runs tests affected by code changes

export PYTHONWARNINGS='ignore'

# Check if this is the first run or if --full is passed
if [ "$1" = "--full" ] || [ "$1" = "-f" ]; then
    echo "Running FULL test suite (refreshing testmon cache)..."
    python -m pytest --testmon-off "$@"
elif [ "$1" = "--nocache" ]; then
    echo "Running tests with fresh testmon cache..."
    rm -f .testmondata
    python -m pytest --testmon "${@:2}"
else
    echo "Running SMART tests (only affected by changes)..."
    python -m pytest --testmon "$@"
fi

ret_code=$?
export PYTHONWARNINGS='default'
exit $ret_code
