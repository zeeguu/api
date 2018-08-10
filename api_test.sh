#!/bin/bash

if mysql -e "use zeeguu_test;" -uzeeguu_test -pzeeguu_test 1>/dev/null 2>/dev/null; then
	echo "Found zeeguu_test databse"
else
	echo "The zeeguu_test database does not exist. "

	echo "To create you must either "
	echo " - provide the password for the mysql root user, or"
	echo " - modify the script accordingly"
	mysql -uroot -p < test_db_creation.sql
fi


export ZEEGUU_API_CONFIG=`pwd`"/default_api.cfg"
export ZEEGUU_CORE_CONFIG=`pwd`"/default_api.cfg"
python -m zeeguu.populate
python -m zeeguu_api
