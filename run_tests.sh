#!/usr/bin/bash
export PYTHONWARNINGS="ignore"
export ZEEGUU_API_CONFIG="./default_api.cfg'
python -m unittest discover -v
export PYTHONWARNINGS="default"
