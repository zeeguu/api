-- What the validator made of a learner's wrong_translation report (roadmap 0c, step 2)
ALTER TABLE word_report
    ADD COLUMN outcome ENUM('valid', 'fixed', 'invalid', 'gave_up', 'not_judged') NULL DEFAULT NULL,
    ADD COLUMN validation_log_id INT NULL DEFAULT NULL,
    ADD COLUMN judged_at DATETIME NULL DEFAULT NULL;
