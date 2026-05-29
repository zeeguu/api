-- First-class per-(user, language) daily audio subscription: config + on/off +
-- schedule. The single source of truth for WHAT to generate and WHEN, replacing
-- the daily_audio_lesson_type_<lang> / _suggestion_<lang> UserPreference rows.
-- The engagement "pause" is NOT stored here; it is computed from the latest
-- lesson (DailyAudioLesson.waiting_paused_for / is_engaged, from #643).
-- A row = subscribed; enabled=0 = turned off (config remembered).
CREATE TABLE daily_audio_subscription (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  language_id INT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  lesson_type VARCHAR(20) NOT NULL,
  raw_suggestion VARCHAR(255) DEFAULT NULL,
  schedule_kind VARCHAR(20) NOT NULL DEFAULT 'daily',
  weekday_mask SMALLINT DEFAULT 127,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_daily_audio_subscription_user_lang UNIQUE (user_id, language_id),
  CONSTRAINT fk_das_user FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
  CONSTRAINT fk_das_language FOREIGN KEY (language_id) REFERENCES language(id)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
