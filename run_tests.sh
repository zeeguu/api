#!/bin/sh

export PYTHONWARNINGS='ignore'
pip install pytest ||
python3 -m pytest #--version 1>/dev/null 2>/dev/null || (echo "installing pytest..." && pip install pytest) && python3 -m pytest
ret_code=$?
export PYTHONWARNINGS='default'
exit $ret_code