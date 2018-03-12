#!/bin/sh
export PYTHONWARNINGS='ignore'
python -m unittest discover tests_zeeguu_api -v
export PYTHONWARNINGS='default'
