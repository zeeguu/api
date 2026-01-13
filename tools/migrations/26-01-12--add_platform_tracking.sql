-- Add platform tracking to user and activity tables
-- Platform values: 0=unknown, 1=web_desktop, 2=web_mobile, 3=ios_app, 4=android_app, 5=extension
-- See zeeguu/core/constants.py for mapping

-- Track where user account was created
ALTER TABLE user ADD COLUMN creation_platform TINYINT UNSIGNED DEFAULT NULL;

-- Track platform for each activity event
ALTER TABLE user_activity_data ADD COLUMN platform TINYINT UNSIGNED DEFAULT NULL;
