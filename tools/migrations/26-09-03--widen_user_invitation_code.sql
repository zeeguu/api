-- user.invitation_code has been narrower in the database than the model has
-- claimed for as long as the core package has lived here: user.py declares
-- db.String(255), the table never followed. Nothing noticed until remove_cohort
-- started prefixing "deleted_" onto the codes of a deleted class's students
-- (c9e020f6). Those 8 characters pushed the value past the real column width,
-- so the UPDATE raised DataError 1406 from inside a Query-invoked autoflush and
-- the whole deletion rolled back -- a teacher trying to delete class 451 got a
-- 500 twice on 2026-09-03 and the class stayed.
--
-- Widening to 255 makes the column mean what the model says, which also removes
-- the same tripwire from signup: invite_code arrives from the client and is
-- written to this column unbounded.
--
-- NOTE: if the current width is small enough that its utf8mb4 byte length is
-- <= 255, this ALTER changes the length prefix from 1 byte to 2 and MySQL has
-- to copy the table rather than do it in place. On `user` that is a short lock,
-- not an instant one -- run it off-peak.

ALTER TABLE user MODIFY invitation_code VARCHAR(255) DEFAULT NULL;
