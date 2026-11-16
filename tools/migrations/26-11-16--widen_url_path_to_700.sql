-- Signed image URLs (Guardian, BRUZZ, ...) have 290-340 character paths;
-- Url.find_or_create returned None for anything over 255, so every article
-- from those feeds was saved without an image.
--
-- Keeps the column's own charset/collation and nullability (the table
-- default is latin1; a bare MODIFY would convert the column). In utf8,
-- 700 chars = 2100 bytes, under InnoDB's 3072-byte key limit for the
-- (domain_name_id, path) unique key. The length prefix is already two bytes
-- (765 > 255), so MySQL 5.7 widens it in place; if it cannot, this fails
-- instead of locking the table (~4.8M rows, 525 MB).

ALTER TABLE url
  MODIFY path VARCHAR(700) CHARACTER SET utf8 COLLATE utf8_bin DEFAULT NULL,
  ALGORITHM=INPLACE, LOCK=NONE;
