-- Add mwe_partner_token_i to bookmark table
-- For separated MWEs (e.g., "rufe...an"), stores the token index of the partner word
-- This allows proper restoration without re-running MWE detection
ALTER TABLE bookmark ADD COLUMN mwe_partner_token_i INTEGER DEFAULT NULL;
