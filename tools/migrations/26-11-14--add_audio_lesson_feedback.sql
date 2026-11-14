-- What learners say about a daily audio lesson after hearing it (pace,
-- repetition, length, and for A0 whether to stay in the situation or move
-- on). One row per lesson and aspect; tapping again changes the value.
-- The next lessons are tuned from these rows (audio_lessons/lesson_tuning.py).

CREATE TABLE audio_lesson_feedback (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    daily_audio_lesson_id INT NOT NULL,
    aspect VARCHAR(20) NOT NULL,
    value VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_audio_lesson_feedback_lesson_aspect (daily_audio_lesson_id, aspect),
    KEY ix_audio_lesson_feedback_user (user_id),
    CONSTRAINT fk_audio_lesson_feedback_user FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
    CONSTRAINT fk_audio_lesson_feedback_lesson FOREIGN KEY (daily_audio_lesson_id) REFERENCES daily_audio_lesson (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Three situations an A0 learner could move on to next, suggested when the
-- lesson is generated (audio_lessons/next_situations.py). NULL for other lessons.
ALTER TABLE daily_audio_lesson ADD COLUMN next_situations JSON NULL;

-- The tuning levels an A0 dialogue was written with ({"pace", "repetition",
-- "length"}, -2..+2). The feedback rows can change afterwards; this cannot.
ALTER TABLE audio_lesson_dialogue ADD COLUMN tuning JSON NULL;
