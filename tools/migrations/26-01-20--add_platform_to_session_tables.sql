-- Add platform tracking to session tables
-- Platform values: 0=unknown, 1=web_desktop, 2=web_mobile, 3=ios_app, 4=android_app, 5=extension
-- See zeeguu/core/constants.py for PLATFORM_* constants

ALTER TABLE user_exercise_session ADD COLUMN platform TINYINT UNSIGNED DEFAULT NULL;
ALTER TABLE user_reading_session ADD COLUMN platform TINYINT UNSIGNED DEFAULT NULL;
ALTER TABLE user_browsing_session ADD COLUMN platform TINYINT UNSIGNED DEFAULT NULL;
ALTER TABLE user_listening_session ADD COLUMN platform TINYINT UNSIGNED DEFAULT NULL;
ALTER TABLE user_watching_session ADD COLUMN platform TINYINT UNSIGNED DEFAULT NULL;
