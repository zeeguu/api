ALTER TABLE
    `session`
ADD
    COLUMN `uuid` char(36) NOT NULL DEFAULT 0
AFTER
    `id`;