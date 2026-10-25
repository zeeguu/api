-- What a learner typed or picked before getting an exercise right (or
-- giving up), one row per wrong attempt. The outcome code only says that an
-- attempt was wrong ("WWC"), not what the learner answered; this keeps the
-- answer, so a word the learner keeps confusing with another meaning ('har
-- det dårligt' answered as 'feel sad') can be told apart from a word they
-- just forget.
--
-- attempt_i orders the wrong answers within the exercise: 0, 1, 2, ...
-- answer is the typed text, or the text of the option picked in a
-- multiple-choice exercise. Binary collation, so 'pa' and 'på' differ.
--
-- A new table, so no rebuild of exercise. Deleting an exercise deletes its
-- wrong answers.

CREATE TABLE exercise_wrong_answer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exercise_id INT NOT NULL,
    attempt_i TINYINT UNSIGNED NOT NULL,
    answer VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,

    UNIQUE KEY uq_exercise_wrong_answer (exercise_id, attempt_i),
    FOREIGN KEY (exercise_id) REFERENCES exercise(id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4;
