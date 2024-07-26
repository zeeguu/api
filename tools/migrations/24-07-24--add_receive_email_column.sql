/*
 adds a receive_email column to the search_subscription table
*/
ALTER TABLE 
    'search_subscription'
ADD 
    COLUMN receive_email BOOLEAN DEFAULT FALSE;

/*
 adds a receive_email column to the search table
*/
ALTER TABLE 
    'Search'
ADD 
    COLUMN receive_email BOOLEAN DEFAULT FALSE;