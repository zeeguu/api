#!/bin/bash

echo "Provide your mysql root password (or modify the script accordingly)"
mysql -e "create database IF NOT EXISTS zeeguu_test; grant all on zeeguu_test.* to 'zeeguu_test'@'localhost' identified by 'zeeguu_test';" -uroot -p
export ZEEGUU_API_CONFIG="./default_api.cfg"
python -m zeeguu_api
