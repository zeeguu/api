#!/bin/bash

if MYSQL_PWD=zeeguu_test mysql -e "use zeeguu_test;" -uzeeguu_test; then
	echo "Found zeeguu_test databse"
else
	echo "The zeeguu_test databse does not exist. Trying to create it..."

	echo "Provide your mysql root password (or modify the script accordingly)"
	mysql -e "create database IF NOT EXISTS zeeguu_test; grant all on zeeguu_test.* to 'zeeguu_test'@'localhost' identified by 'zeeguu_test';" -uroot -p
fi


export ZEEGUU_API_CONFIG="./default_api.cfg"
python -m zeeguu_api
