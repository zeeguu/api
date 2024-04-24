# Convention for naming migrations

Migration file name should be of the form: `yy-mm-dd--oo--description` where

- yy = year
- mm = month
- dd = day
- oo = ordering [optional] - for migrations that have to be done in a certain order
- description = descriptive file name

e.g. `24-04-24--01--add_learning_cycle_column.sql` should be executed before  
`24-04-24--02--update_learning_cycle_for_existing_users.sql`.  