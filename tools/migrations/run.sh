set -u # or set -o nounset

# Example of use
# ./run.sh 24-02-rss_to_feed.sql
# Script expects the four variables below to be defined

mysql -h $ZEEGUU_MYSQL_HOST -u $ZEEGUU_MYSQL_USER -p$ZEEGUU_MYSQL_PASS $ZEEGUU_MYSQL_DB < $1
