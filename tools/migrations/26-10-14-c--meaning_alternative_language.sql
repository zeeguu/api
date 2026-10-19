-- meaning_alternative now also holds translations a learner typed for a
-- meaning ('consult' where an exercise expected 'look up' for 'slå op'),
-- next to the words typed into a cloze ('tænker' for 'synes'). language_id
-- is the language of the typed answer: the meaning's origin language for a
-- cloze, its translation language for a typed translation. It is part of the
-- unique key, so the same string typed on either side stays two verdicts.
--
-- The table is new (26-10-14-b) and small, so the rebuild is cheap.

ALTER TABLE meaning_alternative
    ADD COLUMN language_id INT NULL AFTER meaning_id;

-- Every verdict so far is about a cloze answer: the origin language.
UPDATE meaning_alternative ma
    JOIN meaning m ON m.id = ma.meaning_id
    JOIN phrase p ON p.id = m.origin_id
SET ma.language_id = p.language_id;

ALTER TABLE meaning_alternative
    MODIFY language_id INT NOT NULL COMMENT 'language of the typed answer',
    ADD FOREIGN KEY (language_id) REFERENCES language(id),
    ADD UNIQUE KEY uq_meaning_alternative_language
        (meaning_id, language_id, alternative, context_hash, user_id);

-- After the new key exists: the meaning_id foreign key needs an index that
-- starts with meaning_id, and MySQL refuses to drop the last one.
ALTER TABLE meaning_alternative
    DROP INDEX uq_meaning_alternative;
