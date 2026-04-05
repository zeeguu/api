-- Create audio_lesson_dialogue table
CREATE TABLE IF NOT EXISTS audio_lesson_dialogue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    script TEXT NOT NULL,
    voice_config JSON,
    canonical_suggestion VARCHAR(100) NOT NULL,
    lesson_type VARCHAR(20) NOT NULL,
    title VARCHAR(200),
    language_id INT NOT NULL,
    teacher_language_id INT,
    difficulty_level ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    duration_seconds INT,
    is_general BOOLEAN NOT NULL DEFAULT FALSE,
    created_by VARCHAR(255) NOT NULL,
    FOREIGN KEY (language_id) REFERENCES language(id),
    FOREIGN KEY (teacher_language_id) REFERENCES language(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Index for cache lookups and autocomplete
CREATE INDEX idx_dialogue_lookup ON audio_lesson_dialogue (language_id, teacher_language_id, difficulty_level, lesson_type, canonical_suggestion);
CREATE INDEX idx_dialogue_autocomplete ON audio_lesson_dialogue (language_id, teacher_language_id, difficulty_level, is_general);

-- Add dialogue_lesson to segment_type enum and add FK column
ALTER TABLE daily_audio_lesson_segment
    MODIFY COLUMN segment_type ENUM('intro', 'meaning_lesson', 'dialogue_lesson', 'outro') NOT NULL DEFAULT 'meaning_lesson';

ALTER TABLE daily_audio_lesson_segment
    ADD COLUMN audio_lesson_dialogue_id INT NULL AFTER audio_lesson_meaning_id,
    ADD FOREIGN KEY (audio_lesson_dialogue_id) REFERENCES audio_lesson_dialogue(id) ON DELETE CASCADE;
