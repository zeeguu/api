-- Add word_cefr_level to meaning for caching LLM-assessed difficulty
ALTER TABLE meaning
ADD COLUMN word_cefr_level ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2') DEFAULT NULL
COMMENT 'CEFR level this word/meaning is appropriate for';
