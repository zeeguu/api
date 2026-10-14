-- Reading evidence (ADR 032): gate the practice queue on words the learner
-- demonstrably reads without help. Both columns are written nightly by
-- tools/update_reading_evidence.py and read by the scheduler only for users
-- with the reading_gate feature. Nothing is deleted: a gated word keeps its
-- schedule, and comes back if the gate reopens.
ALTER TABLE user_word
ADD COLUMN reading_log_odds FLOAT DEFAULT NULL
    COMMENT 'log-odds the word is known, from reading; NULL = no evidence',
ADD COLUMN known_from_reading TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'reading_log_odds above the gate, and no polysemy / opt-in';
