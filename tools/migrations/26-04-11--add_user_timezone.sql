-- Store the user's IANA timezone (e.g. "Europe/Copenhagen") so streak math
-- can be done in the user's local day instead of the server's day.
-- NULL means "fall back to server time" — the client populates this on next launch.
ALTER TABLE user
ADD COLUMN timezone VARCHAR(64) NULL;
