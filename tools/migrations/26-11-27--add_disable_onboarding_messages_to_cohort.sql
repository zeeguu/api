ALTER TABLE cohort
    ADD COLUMN disable_onboarding_messages BOOLEAN NOT NULL DEFAULT 0;

UPDATE cohort
SET disable_onboarding_messages = 1
WHERE LOWER(inv_code) IN ('group2s', 'group2e', 'group2d');
