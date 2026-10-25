-- One table for learners' reports about a word (roadmap 0c): replaces
-- exercise_report and meaning_report. Run right before deploying the API
-- that writes word_report; the old API writes the tables dropped here.

CREATE TABLE word_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    meaning_id INT NOT NULL,
    user_word_id INT NULL,
    bookmark_id INT NULL,
    sentence TEXT NULL,
    origin ENUM('exercise', 'reader', 'word_list') NOT NULL,
    exercise_source_id INT NULL,
    kind ENUM('wrong_translation', 'bad_example', 'context_confusing', 'word_not_shown',
              'wrong_highlighting', 'audio_broken', 'wrong_level', 'other') NOT NULL,
    comment TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (meaning_id) REFERENCES meaning (id) ON DELETE CASCADE,
    FOREIGN KEY (user_word_id) REFERENCES user_word (id) ON DELETE SET NULL,
    FOREIGN KEY (bookmark_id) REFERENCES bookmark (id) ON DELETE SET NULL,
    FOREIGN KEY (exercise_source_id) REFERENCES exercise_source (id),
    INDEX idx_word_report_meaning (meaning_id, created_at),
    INDEX idx_word_report_user_bookmark (user_id, bookmark_id)
);

-- Exercise reports: the meaning is the word's at the time of the migration
-- (the closest we have); context_wrong was about the sentence.
INSERT INTO word_report (user_id, meaning_id, user_word_id, bookmark_id, sentence, origin,
                         exercise_source_id, kind, comment, created_at)
SELECT r.user_id, uw.meaning_id, uw.id, r.bookmark_id, r.context_used, 'exercise',
       r.exercise_source_id,
       CASE r.reason WHEN 'context_wrong' THEN 'bad_example' ELSE r.reason END,
       r.comment, r.created_at
FROM exercise_report r
JOIN bookmark b ON b.id = r.bookmark_id
JOIN user_word uw ON uw.id = b.user_word_id;

-- Most exercise reports didn't send the sentence, and three from before
-- 12 Mar 2026 sent '[object Object],…': take the bookmark's own (its context,
-- or for older bookmarks its text)
UPDATE word_report wr
JOIN bookmark b ON b.id = wr.bookmark_id
LEFT JOIN bookmark_context bc ON bc.id = b.context_id
LEFT JOIN text context_text ON context_text.id = bc.text_id
LEFT JOIN text bookmark_text ON bookmark_text.id = b.text_id
SET wr.sentence = COALESCE(context_text.content, bookmark_text.content)
WHERE wr.sentence IS NULL OR wr.sentence LIKE '[object Object]%';

-- Reader reports (meaning only, no sentence)
INSERT INTO word_report (user_id, meaning_id, origin, kind, comment, created_at)
SELECT r.user_id, r.meaning_id, 'reader',
       CASE r.reason WHEN 'bad_examples' THEN 'bad_example'
                     WHEN 'wrong_meaning' THEN 'wrong_translation'
                     ELSE r.reason END,
       r.comment, r.created_at
FROM meaning_report r;

-- Check before dropping: word_report should hold 47 rows (37 + 10 on 25 Oct)
SELECT (SELECT COUNT(*) FROM exercise_report) + (SELECT COUNT(*) FROM meaning_report) AS old_rows,
       (SELECT COUNT(*) FROM word_report) AS new_rows;

DROP TABLE exercise_report;
DROP TABLE meaning_report;
