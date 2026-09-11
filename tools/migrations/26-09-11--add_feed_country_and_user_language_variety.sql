-- Regional varieties: where a feed publishes from, and which variety a learner wants.
--
-- Both sides are ISO 3166-1 alpha-2 so they compare directly: a learner whose
-- Dutch variety is 'BE' wants feeds whose country is 'BE'. NULL on either side
-- means "unknown" / "no preference" and must never exclude anything -- most
-- feeds will stay NULL until they are tagged, and uploaded or shared articles
-- have no feed at all.
--
-- A variety is deliberately not a row in `language`: see
-- zeeguu/core/language/varieties.py for why.

ALTER TABLE feed
ADD COLUMN country CHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 country this feed publishes from; NULL = untagged';

ALTER TABLE user_language
ADD COLUMN variety CHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety the learner wants for this language (nl+BE = Flemish); NULL = no preference';
