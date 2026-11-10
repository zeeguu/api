-- meaning.word_cefr_level was written only by /preview_learning_card, which
-- parsed the first CEFR level out of its level note. The note judges the word
-- for the learner's level ("appropriate for B1 - ..."), and that level was
-- always B1, so the column held the learner's level, not the word's: warum
-- read B1. Every value in it came from there, so clear them all. From now on
-- the translation validator fills it with its own `cefr` for the meaning.
-- Run AFTER the deploy: until then the old code keeps writing B1 here.
UPDATE meaning SET word_cefr_level = NULL WHERE word_cefr_level IS NOT NULL;
