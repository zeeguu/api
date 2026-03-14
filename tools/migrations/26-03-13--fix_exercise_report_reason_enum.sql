ALTER TABLE exercise_report
MODIFY COLUMN reason ENUM('word_not_shown', 'wrong_highlighting', 'context_confusing', 'wrong_translation', 'context_wrong', 'other') NOT NULL;
