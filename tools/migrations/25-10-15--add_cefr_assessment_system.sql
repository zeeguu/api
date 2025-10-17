-- Create CEFR Assessment System (1:1 with Article)
--
-- Separates CEFR assessment data from article table while maintaining simple 1:1 relationship
-- Stores LLM, ML, and Teacher assessments in denormalized format for fast access
--
-- Design benefits:
-- - Keeps article table focused and clean
-- - All assessments in one row (no joins needed)
-- - Simple mental model (1 article = 1 assessment record)
-- - Easy to query: article.cefr_assessment.llm_cefr_level

-- ============================================================================
-- Create article_cefr_assessment table (1:1 with article)
-- ============================================================================

CREATE TABLE article_cefr_assessment
(
    article_id                  INT PRIMARY KEY, -- 1:1 relationship enforced by PRIMARY KEY

    -- LLM assessment (from DeepSeek/Anthropic during article crawling)
    llm_cefr_level              ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')                                      DEFAULT NULL,
    llm_method                  ENUM ('llm_assessed_deepseek', 'llm_assessed_anthropic')                       DEFAULT NULL,
    llm_assessed_at             TIMESTAMP NULL                                                                 DEFAULT NULL,

    -- ML assessment (from ML classifier or naive FK fallback)
    ml_cefr_level               ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')                                                      DEFAULT NULL,
    ml_method                   ENUM ('ml', 'ml_word_freq', 'naive_fk')                                                        DEFAULT NULL,
    ml_assessed_at              TIMESTAMP NULL                                                                                 DEFAULT NULL,

    -- Teacher assessment (manual override or conflict resolution)
    teacher_cefr_level          ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')                                                      DEFAULT NULL,
    teacher_method              ENUM ('teacher_resolution', 'teacher_manual')                                                  DEFAULT NULL,
    teacher_assessed_at         TIMESTAMP NULL                                                                                 DEFAULT NULL,
    teacher_assessed_by_user_id INT                                                                                            DEFAULT NULL
        COMMENT 'Which teacher set this level',

    -- Simplification target level (what level we asked LLM to simplify TO)
    -- This is different from the actual measured level (which might differ from the target)
    simplification_target_level ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2')                                                      DEFAULT NULL
        COMMENT 'Target CEFR level for simplified articles (what level we asked LLM to simplify TO)',

    -- Effective CEFR level - SINGLE SOURCE OF TRUTH for article difficulty
    -- Computed from LLM, ML, and Teacher assessments
    -- Supports both single levels ("B1") and compound levels for adjacent disagreements ("B1/B2")
    effective_cefr_level        ENUM ('A1', 'A2', 'B1', 'B2', 'C1', 'C2',
                                      'A1/A2', 'A2/B1', 'B1/B2', 'B2/C1', 'C1/C2')                                             DEFAULT NULL
        COMMENT 'Effective CEFR level: "B1" (agreement/single), "B1/B2" (adjacent disagreement), "B2" (large disagreement picks higher)',


    -- Foreign keys
    FOREIGN KEY (article_id) REFERENCES article (id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_assessed_by_user_id) REFERENCES user (id) ON DELETE SET NULL,

    -- Indexes for filtering and sorting
    INDEX idx_llm_cefr_level (llm_cefr_level),
    INDEX idx_ml_cefr_level (ml_cefr_level),
    INDEX idx_teacher_cefr_level (teacher_cefr_level),
    INDEX idx_effective_cefr_level (effective_cefr_level),
    INDEX idx_teacher_assessed_by (teacher_assessed_by_user_id)

) COMMENT '1:1 assessment data for articles - stores LLM, ML, and Teacher CEFR assessments';


-- ============================================================================
-- Backfill simplification_target_level for existing simplified articles
-- ============================================================================

-- For articles that were simplified (parent_article_id IS NOT NULL),
-- set the simplification_target_level to match their cefr_level

-- First, ensure all simplified articles have an assessment record
INSERT INTO article_cefr_assessment (article_id, simplification_target_level)
SELECT a.id, a.cefr_level
FROM article a
WHERE a.parent_article_id IS NOT NULL
  AND a.cefr_level IS NOT NULL
  AND NOT EXISTS (SELECT 1
                  FROM article_cefr_assessment aca
                  WHERE aca.article_id = a.id);

-- Then update existing records
UPDATE article_cefr_assessment aca
    JOIN article a ON aca.article_id = a.id
SET aca.simplification_target_level = a.cefr_level
WHERE a.parent_article_id IS NOT NULL
  AND a.cefr_level IS NOT NULL
  AND aca.simplification_target_level IS NULL;


-- ============================================================================
-- Mark article.cefr_level as deprecated
-- ============================================================================

-- Add comment to article.cefr_level marking it as legacy/deprecated
-- The SINGLE SOURCE OF TRUTH is now article_cefr_assessment.effective_cefr_level
ALTER TABLE article
MODIFY COLUMN cefr_level ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2')
COMMENT 'DEPRECATED: Use article_cefr_assessment.effective_cefr_level instead. Kept for backward compatibility only.';


-- ============================================================================
-- Instructions for data migration
-- ============================================================================

-- After running this migration, run the backfill script to populate
-- article_cefr_assessment table from existing article.cefr_level data:
--
--   source ~/.venvs/z_env/bin/activate && python -m tools.backfill_cefr_assessments
--
-- This will:
-- 1. Analyze article data (parent_article_id, simplification_ai_generator_id) to determine assessment type
-- 2. Create article_cefr_assessment records with appropriate columns populated
-- 3. Compute and cache effective_cefr_level values (supporting compound levels like "B1/B2")
