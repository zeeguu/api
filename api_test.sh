#!/bin/bash

if mysql -e "use zeeguu_test;" -uzeeguu_test -pzeeguu_test 1>/dev/null 2>/dev/null; then
	echo "Found zeeguu_test databse"
else
	echo "The zeeguu_test database does not exist. "

	echo "To create you must either "
	echo " - provide the password for the mysql root user, or"
	echo " - modify the script accordingly"
	mysql -e "create database IF NOT EXISTS zeeguu_test; grant all on zeeguu_test.* to 'zeeguu_test'@'localhost' identified by 'zeeguu_test';" -uroot -p
fi


export ZEEGUU_API_CONFIG="./default_api.cfg"
export ZEEGUU_CORE_CONFIG="./default_api.cfg"
python3.6 -m zeeguu.populate
python -m zeeguu_api
