import sys
import MySQLdb

"""
This file contains the scripts for migrating the old Zeeguu database to the new version for this project.
"""

"""
For now fixed code for the below information of database
"""
host = "localhost"
database = 'zeeguu_test'
user = "root"
password = "12345678"


def main():
    """
    This connects to and upgrades the database
    :param:
    :return:
    """
    try:
        connection = MySQLdb.connect(host=host,
                                     user=user,
                                     passwd=password,
                                     db=database)

    except MySQLdb.Error as e:
        print("Error %d: %s" % (e.args[0], e.args[1]))
        sys.exit(1)

    cursor = connection.cursor()

    upgrade_cohort_db(cursor, database)

    """
    this doesn't do anything but it is good to see if we update db correctly
    """
    get_cohort(cursor)

    disconnect_db(cursor, connection)


def upgrade_cohort_db(cursor, database):
    """
    This upgrades the cohort database table
    :param cursor:
    :param database:
    :return:
    """

    """
    Rename invitation_code to inv_code column
    """
    cursor.execute("SELECT * FROM information_schema.COLUMNS "
                   "WHERE TABLE_SCHEMA = '" + database +
                   "' AND TABLE_NAME = 'cohort' "
                   "AND COLUMN_NAME = 'invitation_code'")
    result = cursor.fetchall()
    if result:
        cursor.execute("ALTER TABLE cohort "
                       "Change invitation_code inv_code varchar(255) ")
        cursor.execute("ALTER TABLE cohort "
                       "ADD UNIQUE (inv_code) ")
        cursor.execute("SELECT id, name, inv_code FROM cohort")
        rows = cursor.fetchall()
        for row in rows:
            """
            if no class has inv_code, set the name as same as inv_code
            """
            if row[2] is None:
                q = "UPDATE cohort SET inv_code = %s WHERE id = %s" 
                data = (row[1], row[0])
                cursor.execute(q, data)

    """
    Add column max_students
    """
    cursor.execute("SELECT * FROM information_schema.COLUMNS "
                   "WHERE TABLE_SCHEMA = '" + database +
                   "' AND TABLE_NAME = 'cohort' "
                   "AND COLUMN_NAME = 'max_students'")
    result = cursor.fetchall()
    if not result:
        cursor.execute("ALTER TABLE cohort "
                       "ADD max_students int NOT NULL DEFAULT 30")

    """
    Add class_language_id column and name the foreign key
    """
    cursor.execute("SELECT * FROM information_schema.COLUMNS "
                   "WHERE TABLE_SCHEMA = '" + database +
                   "' AND TABLE_NAME = 'cohort' "
                   "AND COLUMN_NAME = 'language_id'")
    result = cursor.fetchall()
    if not result:
        cursor.execute("ALTER TABLE cohort "
                       "ADD language_id int(3)")
        cursor.execute("ALTER TABLE cohort "
                       "ADD CONSTRAINT FK_language_id "
                       "FOREIGN KEY (language_id) REFERENCES language (id)")


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
