-- Fix foreign key constraint that still references old ai_models table name
-- The ai_models table was renamed to ai_generator in 25-07-31 migration,
-- but the foreign key constraint wasn't properly updated

-- Drop the old foreign key constraint
ALTER TABLE `zeeguu_test`.`article` 
DROP FOREIGN KEY `article_ibfk_8`;

-- Add the corrected foreign key constraint pointing to ai_generator
ALTER TABLE `zeeguu_test`.`article`
ADD CONSTRAINT `fk_article_simplification_ai_generator`
  FOREIGN KEY (`simplification_ai_generator_id`) 
  REFERENCES `ai_generator` (`id`) 
  ON DELETE SET NULL 
  ON UPDATE NO ACTION;