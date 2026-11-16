-- Signed image URLs (Guardian, BRUZZ, ...) have 290-340 character paths;
-- Url.find_or_create returned None for anything over 255, so every article
-- from those feeds was saved without an image.
--
-- 700 chars keeps the (path, domain_name_id) unique key under InnoDB's
-- 3072-byte prefix limit even in utf8mb4 (large_prefix ON, row format
-- DYNAMIC in prod). Widening a VARCHAR whose length prefix is already two
-- bytes is in place on MySQL 5.7; if it is not, this fails rather than
-- locking the table (~4.8M rows, 525 MB).

ALTER TABLE url MODIFY path VARCHAR(700), ALGORITHM=INPLACE, LOCK=NONE;
