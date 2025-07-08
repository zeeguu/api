-- Add meaning frequency with optimized schema and phrase type classification
-- This migration combines frequency classification and phrase type for the meaning table

-- Create models table for AI model metadata
CREATE TABLE ai_models
(
    id          INT PRIMARY KEY AUTO_INCREMENT,
    model_name  VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- Insert current model
INSERT INTO ai_models (model_name, description)
VALUES ('claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet used for meaning frequency classification');

-- Add frequency columns to meaning table
ALTER TABLE meaning
    ADD COLUMN frequency ENUM ('UNIQUE', 'COMMON', 'UNCOMMON', 'RARE')
        DEFAULT NULL
        COMMENT 'How frequently this particular meaning is used';

ALTER TABLE meaning
    ADD COLUMN frequency_model_id INT
        DEFAULT NULL
        COMMENT 'AI model used to generate the frequency';

ALTER TABLE meaning
    ADD COLUMN frequency_manually_validated BOOLEAN
        DEFAULT FALSE
        COMMENT 'Whether the AI-generated frequency has been validated by a human';

-- Add phrase type classification
ALTER TABLE meaning 
    ADD COLUMN phrase_type ENUM('SINGLE_WORD', 'COLLOCATION', 'IDIOM', 'EXPRESSION', 'MULTI_WORD') 
        DEFAULT NULL 
        COMMENT 'Type of phrase/expression (single word, idiom, collocation, expression, or arbitrary multi-word selection)';

ALTER TABLE meaning
    ADD COLUMN phrase_type_manually_validated BOOLEAN
        DEFAULT FALSE
        COMMENT 'Whether the AI-generated phrase type has been validated by a human';

-- Add foreign key constraint
ALTER TABLE meaning
    ADD CONSTRAINT fk_meaning_frequency_model
        FOREIGN KEY (frequency_model_id) REFERENCES ai_models (id);

-- Example usage:
-- Get model ID: SELECT id FROM ai_models WHERE model_name = 'claude-3-5-sonnet-20241022';
-- UPDATE meaning SET 
--   frequency = 'COMMON',
--   frequency_model_id = 1,
--   frequency_manually_validated = FALSE,
--   phrase_type = 'SINGLE_WORD',
--   phrase_type_manually_validated = FALSE
-- WHERE id = 123;

-- Query meanings with model info:
-- SELECT m.*, am.model_name, am.description
-- FROM meaning m 
-- LEFT JOIN ai_models am ON m.frequency_model_id = am.id
-- WHERE m.frequency IS NOT NULL;

-- Find single words vs expressions:
-- SELECT phrase_type, COUNT(*) FROM meaning WHERE phrase_type IS NOT NULL GROUP BY phrase_type;

-- Find idioms that need frequency classification:
-- SELECT * FROM meaning WHERE phrase_type = 'IDIOM' AND frequency IS NULL;

-- Find arbitrary multi-word selections:
-- SELECT * FROM meaning WHERE phrase_type = 'MULTI_WORD';