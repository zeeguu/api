-- Fix remaining foreign key constraints that reference ai_models table
-- This allows us to safely drop the old ai_models table after it was renamed to ai_generator

-- First check if the old table still exists, and if so, transfer any remaining data
-- Then update all foreign key constraints to point to ai_generator instead

-- Fix meaning table foreign key constraint 
-- (frequency_model_id should point to ai_generator, not ai_models)
ALTER TABLE `zeeguu_test`.`meaning`
    DROP FOREIGN KEY `fk_meaning_frequency_model`;

ALTER TABLE `zeeguu_test`.`meaning`
    ADD CONSTRAINT `fk_meaning_frequency_ai_generator`
        FOREIGN KEY (`frequency_model_id`)
            REFERENCES `ai_generator` (`id`)
            ON DELETE SET NULL
            ON UPDATE NO ACTION;

-- Fix example_sentence table foreign key constraint if it exists
-- Check if there are any other constraints pointing to ai_models
-- Note: example_sentence_ai_generator_FK should already point to ai_generator from the 25-07-31 migration

-- Now we can safely drop the ai_models table since all references have been updated
-- DROP TABLE IF EXISTS `zeeguu_test`.`ai_models`;
-- DROP TABLE IF EXISTS `zeeguu_test`.`ai_model`;

