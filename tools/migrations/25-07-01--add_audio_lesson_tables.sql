-- Migration: Add audio lesson tables
-- Date: 2025-07-01
-- Description: Creates tables for audio lessons linked to meanings and daily audio lessons for users

-- Table for individual audio lessons per meaning
CREATE TABLE audio_lesson_meaning
(
    id               INT(11)      NOT NULL AUTO_INCREMENT,
    meaning_id       INT(11)      NOT NULL,
    script           TEXT         NOT NULL,
    voice_config     JSON,
    difficulty_level ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    lesson_type      VARCHAR(50) DEFAULT 'contextual_examples',
    duration_seconds INT,
    created_by       VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (meaning_id) REFERENCES meaning (id) ON DELETE CASCADE,
    INDEX idx_meaning (meaning_id),
    INDEX idx_difficulty (difficulty_level)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- Table for daily audio lessons (combines multiple meaning lessons with user interaction tracking)
CREATE TABLE daily_audio_lesson
(
    id                     INT(11)      NOT NULL AUTO_INCREMENT,
    user_id                INT(11)      NOT NULL,
    voice_config           JSON,
    duration_seconds       INT,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by             VARCHAR(255) NOT NULL,
    
    -- User interaction tracking
    recommended_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at           TIMESTAMP NULL DEFAULT NULL,
    listened_count         INT DEFAULT 0,
    last_paused_at         TIMESTAMP NULL DEFAULT NULL,
    pause_position_seconds INT DEFAULT 0,
    
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_user_recommended (user_id, recommended_at)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- Wrapper scripts (intro/outro) for daily audio lessons
CREATE TABLE daily_audio_lesson_wrapper
(
    id               INT(11)                 NOT NULL AUTO_INCREMENT,
    script           TEXT                    NOT NULL,
    wrapper_type     ENUM ('intro', 'outro') NOT NULL,
    duration_seconds INT,
    created_by       VARCHAR(255)            NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_wrapper_type (wrapper_type)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- Segments within daily audio lessons (intro, meaning lessons, outro)
CREATE TABLE daily_audio_lesson_segment
(
    id                      INT(11)                                   NOT NULL AUTO_INCREMENT,
    daily_audio_lesson_id        INT(11)                                   NOT NULL,
    segment_type                 ENUM ('intro', 'meaning_lesson', 'outro') NOT NULL DEFAULT 'meaning_lesson',
    audio_lesson_meaning_id      INT(11)                                            DEFAULT NULL,
    daily_audio_lesson_wrapper_id INT(11)                                            DEFAULT NULL,
    sequence_order               INT                                       NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (daily_audio_lesson_id) REFERENCES daily_audio_lesson (id) ON DELETE CASCADE,
    FOREIGN KEY (audio_lesson_meaning_id) REFERENCES audio_lesson_meaning (id) ON DELETE CASCADE,
    FOREIGN KEY (daily_audio_lesson_wrapper_id) REFERENCES daily_audio_lesson_wrapper (id) ON DELETE CASCADE,
    INDEX idx_lesson_order (daily_audio_lesson_id, sequence_order)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;