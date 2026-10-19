-- Meaning lessons we could not get written, per prompt version, so the audio
-- word selector stops picking the word and the overnight precompute stops
-- paying for the same refusal every night.
--
-- reason:
--   not_a_script  the model wrote prose instead of a script (NotAScript): it
--                 declined the word, or said our data was wrong. detail holds
--                 its words, which need a person (see NotAScript).
--   not_correct   the script still taught the word wrong after one rewrite
--                 (the lesson check, 2026-10-18). detail holds the problems.
--
-- A refusal holds for its prompt_version only: a new prompt may succeed, so a
-- prompt bump retries every refused word once. The word stays in exercises;
-- only its audio lesson failed. A pair found WRONG is recorded too, and its
-- meaning is also marked INVALID.

CREATE TABLE audio_lesson_refusal (
    id INT AUTO_INCREMENT PRIMARY KEY,
    meaning_id INT NOT NULL,
    teacher_language_id INT NOT NULL,
    prompt_version VARCHAR(50) NOT NULL,
    reason ENUM('not_a_script', 'not_correct') NOT NULL,
    detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_audio_lesson_refusal (meaning_id, teacher_language_id, prompt_version),
    FOREIGN KEY (meaning_id) REFERENCES meaning(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_language_id) REFERENCES language(id)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
