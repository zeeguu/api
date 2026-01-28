#!/bin/sh
# Run all tests

export PYTHONWARNINGS='ignore'

echo "Running test suite..."
python -m pytest "$@"

ret_code=$?
export PYTHONWARNINGS='default'
exit $ret_code
