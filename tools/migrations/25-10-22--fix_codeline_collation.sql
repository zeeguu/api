-- Fix FMD (Flask Monitoring Dashboard) database collation mismatch
-- The CodeLine table is created by FMD package for profiling
-- It was created with latin1_swedish_ci collation which causes conflicts
-- when comparing with utf8mb4 data from the application

-- IMPORTANT: This migration needs to run on the FMD database, not the main Zeeguu database
-- If FMD uses a separate database (fmd_mysql), you'll need to run this separately on that database
-- Or you can use the command line to specify the database:
-- mysql -u ${FMD_MYSQL_USER} -p${FMD_MYSQL_USER_PASS} ${FMD_MYSQL_DB} < this_file.sql

-- Convert CodeLine table to utf8mb4
ALTER TABLE `CodeLine` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Also convert other FMD tables to be safe
ALTER TABLE `Request` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
ALTER TABLE `Endpoint` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Set the database default collation for future tables
ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
