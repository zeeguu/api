import sys
import MySQLdb

"""
This file contains the scripts for converting the new Zeeguu database back to the old version for this project.
"""

"""
For now fixed code for the below information of database
"""
host = "localhost"
user = "root"
password = "12345678"
database = 'zeeguu_test'


def main():
    """
    This connects to and downgrades the database
    :param:
    :return:
    """
    try:
        connection = MySQLdb.connect (host = host,
                                      user = user,
                                      passwd = password,
                                      db = database)
    except MySQLdb.Error as e:
        print("Error %d: %s" % (e.args[0], e.args[1]))
        sys.exit(1)

    cursor = connection.cursor()

    downgrade_cohort_db(cursor, database)

    """
    This doesn't do anything but it is good to see if we update db correctly
    """
    get_cohort(cursor)

    disconnect_db(cursor, connection)


def downgrade_cohort_db(cursor, database):
    """
    This downgrades the cohort database table
    :param cursor:
    :param database:
    :return:
    """

    """
    Drop max_students column
    """
    cursor.execute("SELECT * FROM information_schema.COLUMNS "
                   "WHERE TABLE_SCHEMA = '" + database +
                   "' AND TABLE_NAME = 'cohort' "
                   "AND COLUMN_NAME = 'max_students'")
    result = cursor.fetchone()
    if result:
        cursor.execute("ALTER TABLE cohort "
                       "DROP COLUMN max_students")

    """
    Remove foreign key and drop column language_id
    """
    cursor.execute("SELECT * FROM information_schema.COLUMNS "
                   "WHERE TABLE_SCHEMA = '" + database +
                   "' AND TABLE_NAME = 'cohort' "
                   "AND COLUMN_NAME = 'language_id'")
    result = cursor.fetchone()
    if result:
        cursor.execute("ALTER TABLE cohort DROP FOREIGN KEY FK_language_id")
        cursor.execute("ALTER TABLE cohort "
                       "DROP COLUMN language_id")

    """
    Change inv_code back to invitation_code
    """
    cursor.execute("SELECT * FROM information_schema.COLUMNS "
                   "WHERE TABLE_SCHEMA = '" + database +
                   "' AND TABLE_NAME = 'cohort' "
                   "AND COLUMN_NAME = 'inv_code'")
    result = cursor.fetchone()
    if result:
        cursor.execute("ALTER TABLE cohort "
                       "Change inv_code invitation_code char(50) NOT NULL")


def get_cohort(cursor):
    """
    Checkout the cohort table
    :param cursor:
    :return:
    """
    query = "SELECT * FROM cohort "
    cursor.execute(query)
    print('''SELECT * FROM cohort:''')
    result = cursor.fetchall()
    for r in result:
        print(r)
    return result


def disconnect_db(cursor, connection):
    """
    Disconnect the database
    :param cursor:
    :param connection:
    :return:
    """
    cursor.close()
    connection.close()


if __name__ == '__main__':
    main()