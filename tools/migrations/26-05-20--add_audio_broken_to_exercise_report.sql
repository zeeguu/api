-- tools/migrations/26-05-20--add_audio_broken_to_exercise_report.sql
-- Adds 'audio_broken' as a valid reason for exercise reports, so the new
-- "Audio is broken / unclear" chip in the report dialog can submit a clean
-- analytics bucket instead of being lumped under 'other'.

ALTER TABLE exercise_report
MODIFY COLUMN reason ENUM(
    'word_not_shown',
    'wrong_highlighting',
    'context_confusing',
    'wrong_translation',
    'context_wrong',
    'audio_broken',
    'other'
) NOT NULL;
