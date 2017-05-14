#!/bin/sh
export PYTHONWARNINGS='ignore'
export ZEEGUU_API_CONFIG="./default_api.cfg"
echo $ZEEGUU_API_CONFIG
python -m unittest discover zeeguu_api/tests -v
export PYTHONWARNINGS='default'
