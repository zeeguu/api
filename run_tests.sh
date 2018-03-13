#!/bin/sh

export PYTHONWARNINGS='ignore'
python -m pytest || echo "make sure to install pytest (pip install pytest)"
export PYTHONWARNINGS='default'
