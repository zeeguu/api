-- Rename ai_models table to ai_generator (singular, more descriptive)
RENAME TABLE `zeeguu_test`.`ai_models` TO `zeeguu_test`.`ai_generator`;

-- Add prompt_version column to ai_generator table
ALTER TABLE `zeeguu_test`.`ai_generator` 
ADD COLUMN `prompt_version` varchar(50) DEFAULT NULL;

-- Update existing article table to use new naming
ALTER TABLE `zeeguu_test`.`article` 
CHANGE COLUMN `simplification_ai_model_id` `simplification_ai_generator_id` int DEFAULT NULL;