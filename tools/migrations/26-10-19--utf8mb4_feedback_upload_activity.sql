-- user_feedback was latin1 and article_upload / user_activity_data were
-- 3-byte utf8, so 4-byte characters (emoji) were rejected on insert
-- ("Incorrect string value") and utf8mb4 parameters clashed in WHERE
-- comparisons ("Illegal mix of collations (utf8_bin,IMPLICIT) and
-- (utf8mb4_general_ci,COERCIBLE)"). The _bin tables stay binary.
--
-- MySQL 5.7 rebuilds each table; user_activity_data (~300MB) blocks
-- writes for a minute or two, so run off-peak.

ALTER TABLE user_feedback CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE article_upload CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
ALTER TABLE user_activity_data CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
