-- Populate language_id for existing daily audio lessons
-- This updates all existing lessons to have the correct language_id based on their content

-- Update language_id for existing lessons by looking at the language of the meanings in the lesson
UPDATE daily_audio_lesson dal
JOIN (
    -- Get the language_id from the first meaning segment in each lesson
    SELECT 
        dal.id as lesson_id,
        MIN(p.language_id) as language_id  -- Use MIN to get a single language_id per lesson
    FROM daily_audio_lesson dal
    JOIN daily_audio_lesson_segment dals ON dals.daily_audio_lesson_id = dal.id
    JOIN audio_lesson_meaning alm ON alm.id = dals.audio_lesson_meaning_id
    JOIN meaning m ON m.id = alm.meaning_id
    JOIN phrase p ON p.id = m.origin_id
    WHERE dals.segment_type = 'meaning_lesson'
    AND dal.language_id IS NULL
    GROUP BY dal.id
) AS lesson_languages ON lesson_languages.lesson_id = dal.id
SET dal.language_id = lesson_languages.language_id
WHERE dal.language_id IS NULL;

-- Verify the update
SELECT 
    COUNT(*) as total_lessons,
    SUM(CASE WHEN language_id IS NULL THEN 1 ELSE 0 END) as lessons_without_language,
    SUM(CASE WHEN language_id IS NOT NULL THEN 1 ELSE 0 END) as lessons_with_language
FROM daily_audio_lesson;

-- Show distribution of lessons by language
SELECT 
    l.code as language_code,
    l.name as language_name,
    COUNT(dal.id) as lesson_count
FROM daily_audio_lesson dal
JOIN language l ON l.id = dal.language_id
GROUP BY l.id
ORDER BY lesson_count DESC;