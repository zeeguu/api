-- purpose: what the code was issued for. 'reset' for the codes mailed by
-- /send_code, 'verify' for every email-confirmation code. Each endpoint only
-- accepts codes of its own purpose. Rows written before this migration are
-- NULL and are accepted by neither; codes live 15 minutes, so this only
-- affects a code requested in the minutes around the deploy.
--
-- attempts: how many times a code has been submitted. A code stops being
-- accepted after a handful of submissions (UniqueCode.MAX_ATTEMPTS). Kept in
-- the row rather than in the rate limiter, whose counters are per worker and
-- reset on every restart.

ALTER TABLE unique_code
    ADD COLUMN purpose VARCHAR(16) NULL,
    ADD COLUMN attempts INT NOT NULL DEFAULT 0;
