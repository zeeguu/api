/*
 removes all searches and search aubscriptions from the database, which ensures no duplicates. 
*/
TRUNCATE search_subscription;

TRUNCATE search_filter;

DELETE FROM Search;
/* This is delete from search, because otherwise you would need to remove the foreign key constraints and recreate them. 
    This way you do not have to do that. */