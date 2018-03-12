#!/bin/sh
export PYTHONWARNINGS='ignore'
python -m unittest discover zeeguu_api/tests -v
export PYTHONWARNINGS='default'
