-- Where each login session was created (constants.PLATFORM_*: 1 web desktop,
-- 2 web mobile, 3 iOS app, 4 Android app, 5 extension). The session token
-- stays on the device or browser that logged in, so this is the platform of
-- every request carrying it. Sessions created before this stay NULL.
--
-- Nullable column at the end of the table: an instant ALTER on MySQL 8.

ALTER TABLE session ADD COLUMN platform SMALLINT NULL;
