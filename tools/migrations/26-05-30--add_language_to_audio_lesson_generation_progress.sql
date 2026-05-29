-- Record which learned-language an in-flight generation is for, so the app can
-- only adopt a progress record into its UI when it matches the language the
-- user is currently viewing (prevents a Danish view from showing a Dutch
-- generation's progress, mislabeled).
ALTER TABLE audio_lesson_generation_progress
ADD COLUMN language_id INT DEFAULT NULL,
ADD CONSTRAINT fk_alpg_language FOREIGN KEY (language_id) REFERENCES language(id);
