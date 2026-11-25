-- A0 lessons: review cards and what each lesson reviewed.
--
-- audio_lesson_card: one thing the learner answered in a lesson, written when
-- the lesson is made from its [answer] lines (audio_lessons/lesson_markup.cards).
-- A question: the Teacher's question (prompt_voice 'teacher') and the answer.
-- An exchange: the Teacher's setup, the Other person's line (prompt_voice
-- 'man' or 'woman') and the answer. answer_voice is the learner's voice then:
-- a card is reviewed only while the learner has that voice. Stored once, so a
-- review keeps pointing at the same card when the parsing changes.
--
-- audio_lesson_review: what a lesson reviews, in order. Code chooses it and
-- places it (audio_lessons/lesson_review.py), spacing each card's reviews
-- further apart; the model does not take part. kind 'card' (card_id set), or
-- 'dialogue' (a whole earlier dialogue answered in the learner's role, for a
-- lesson from before cards; card_id NULL).
--
-- marked_script: the script as the model wrote it, with markers
-- (audio_lessons/lesson_markup.py). The stored script is its expansion, with
-- the review added.

CREATE TABLE audio_lesson_card (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dialogue_id INT NOT NULL,
    position INT NOT NULL,
    setup VARCHAR(500) NULL,
    prompt_voice VARCHAR(9) NOT NULL,
    prompt VARCHAR(500) NOT NULL,
    answer_voice VARCHAR(5) NOT NULL,
    answer VARCHAR(500) NOT NULL,
    UNIQUE KEY uq_card_position (dialogue_id, position),
    FOREIGN KEY (dialogue_id) REFERENCES audio_lesson_dialogue(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audio_lesson_review (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dialogue_id INT NOT NULL,
    reviewed_dialogue_id INT NOT NULL,
    kind VARCHAR(10) NOT NULL,
    card_id INT NULL,
    position INT NOT NULL,
    UNIQUE KEY uq_review_position (dialogue_id, position),
    KEY idx_reviewed (reviewed_dialogue_id),
    FOREIGN KEY (dialogue_id) REFERENCES audio_lesson_dialogue(id),
    FOREIGN KEY (reviewed_dialogue_id) REFERENCES audio_lesson_dialogue(id),
    FOREIGN KEY (card_id) REFERENCES audio_lesson_card(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE audio_lesson_dialogue ADD COLUMN marked_script TEXT NULL;
