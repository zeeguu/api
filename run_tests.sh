#!/bin/sh

export PYTHONWARNINGS='ignore'
python3 -m pytest --version 1>/dev/null 2>/dev/null || (echo "installing pytest..." && pip3 install pytest) && python3 -m pytest
export PYTHONWARNINGS='default'
