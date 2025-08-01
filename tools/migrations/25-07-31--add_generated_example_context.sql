-- First, rename ai_models table to ai_generator
RENAME TABLE `zeeguu_test`.`ai_models` TO `zeeguu_test`.`ai_generator`;

-- Add prompt_version column to ai_generator table
ALTER TABLE `zeeguu_test`.`ai_generator` 
ADD COLUMN `prompt_version` varchar(50) DEFAULT NULL;

-- Update existing article table to use new naming
ALTER TABLE `zeeguu_test`.`article` 
CHANGE COLUMN `simplification_ai_model_id` `simplification_ai_generator_id` int DEFAULT NULL;

-- Add ExampleSentence context type if it doesn't exist
INSERT IGNORE INTO
    `zeeguu_test`.`context_type` (`type`)
VALUES
    ('ExampleSentence');

-- Create the example_sentence table to store example sentences
CREATE TABLE `zeeguu_test`.`example_sentence` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sentence` TEXT NOT NULL,
  `translation` TEXT DEFAULT NULL,
  `language_id` int NOT NULL,
  `meaning_id` int NOT NULL,
  `cefr_level` varchar(10) DEFAULT NULL,
  `ai_generator_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `example_sentence_language_FK` (`language_id`),
  KEY `example_sentence_meaning_FK` (`meaning_id`),
  KEY `example_sentence_ai_generator_FK` (`ai_generator_id`),
  KEY `example_sentence_user_FK` (`user_id`),
  CONSTRAINT `example_sentence_language_FK` FOREIGN KEY (`language_id`) REFERENCES `language` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `example_sentence_meaning_FK` FOREIGN KEY (`meaning_id`) REFERENCES `meaning` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `example_sentence_ai_generator_FK` FOREIGN KEY (`ai_generator_id`) REFERENCES `ai_generator` (`id`) ON DELETE SET NULL ON UPDATE NO ACTION,
  CONSTRAINT `example_sentence_user_FK` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE SET NULL ON UPDATE NO ACTION
);

-- Create the example_sentence_context mapping table
CREATE TABLE `zeeguu_test`.`example_sentence_context` (
  `id` int NOT NULL AUTO_INCREMENT,
  `bookmark_id` int NOT NULL,
  `example_sentence_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `example_sentence_context_bookmark_FK` (`bookmark_id`),
  KEY `example_sentence_context_example_FK` (`example_sentence_id`),
  CONSTRAINT `example_sentence_context_bookmark_FK` FOREIGN KEY (`bookmark_id`) REFERENCES `bookmark` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION,
  CONSTRAINT `example_sentence_context_example_FK` FOREIGN KEY (`example_sentence_id`) REFERENCES `example_sentence` (`id`) ON DELETE CASCADE ON UPDATE NO ACTION
);

-- Add unique constraint to context_type to prevent duplicates
ALTER TABLE `zeeguu_test`.`context_type` 
ADD CONSTRAINT unique_context_type UNIQUE (`type`);