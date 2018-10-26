#!/bin/sh

export PYTHONWARNINGS='ignore'
python -m pytest --version 1>/dev/null 2>/dev/null || (echo "installing pytest..." && pip install pytest) && python -m pytest
ret_code=$?
export PYTHONWARNINGS='default'
exit $ret_code