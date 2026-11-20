-- A0 lessons: what a lesson reviews from earlier lessons, in order. Code
-- chooses it and places it (audio_lessons/lesson_review.py), spacing each
-- item's reviews further apart; the model does not take part. The spacing
-- reads this table.
--
-- kind: 'dialogue' (an earlier lesson's dialogue, answered in the learner's
-- role); later 'question' (one [ask]/[answer] pair from an earlier lesson's
-- marked_script, item = its index there). item is NULL for a dialogue.
--
-- marked_script: the script as the model wrote it, with markers
-- (audio_lessons/lesson_markup.py). The stored script is its expansion, with
-- the review added. Kept so a lesson can be expanded again without the model, and so
-- prompts can be compared on what the model wrote.

CREATE TABLE audio_lesson_review (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dialogue_id INT NOT NULL,
    reviewed_dialogue_id INT NOT NULL,
    kind VARCHAR(10) NOT NULL DEFAULT 'dialogue',
    item INT NULL,
    position INT NOT NULL,
    UNIQUE KEY uq_review_position (dialogue_id, position),
    KEY idx_reviewed (reviewed_dialogue_id),
    FOREIGN KEY (dialogue_id) REFERENCES audio_lesson_dialogue(id),
    FOREIGN KEY (reviewed_dialogue_id) REFERENCES audio_lesson_dialogue(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE audio_lesson_dialogue ADD COLUMN marked_script TEXT NULL;
