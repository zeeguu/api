#!/bin/bash
MYSQL=`which mysql`
DBNAME='zeeguu_test'
DBUSER='zeeguu_test'
DBPASS='zeeguu_test'

Q1="CREATE DATABASE IF NOT EXISTS $DBNAME;"
Q2="GRANT USAGE ON *.* TO $DBUSER@localhost IDENTIFIED BY '$DBPASS';"
Q3="GRANT ALL PRIVILEGES ON $DBNAME.* TO $DBUSER@localhost;"
Q4="FLUSH PRIVILEGES;"
SQL="${Q1}${Q2}${Q3}${Q4}"

$MYSQL -uroot -p -e "$SQL"