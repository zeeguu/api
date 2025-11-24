-- Drop the legacy user.cohort_id column
-- This field was deprecated in favor of the UserCohortMap many-to-many relationship
-- It was never mapped in the SQLAlchemy User model and only used by deprecated endpoints
-- Its foreign key constraint was preventing cohort deletion

-- Drop the foreign key constraint first
ALTER TABLE user
DROP FOREIGN KEY user_ibfk_3;

-- Drop the column
ALTER TABLE user
DROP COLUMN cohort_id;
