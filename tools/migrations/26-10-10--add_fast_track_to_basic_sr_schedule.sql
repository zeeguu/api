-- Fast progression (zeeguu/api#796): every level starts on the fast track, and
-- while a word is on it, a clean answer ("C": first try, no hint) moves it up a
-- level at once. The first answer at a level that is not clean takes the word
-- off the fast track until its next level. The schedule could not tell "just
-- arrived at this level" from "already stumbled here" (both are interval 0),
-- hence the column.
--
-- Kept up to date for every user; only users with the fast_progression feature
-- move faster. So the comparison group shows which of its words would have
-- stayed on the fast track.
--
-- Existing schedules start on it: their current level's history is unknown,
-- and the column has no effect without the feature.
ALTER TABLE basic_sr_schedule
ADD COLUMN fast_track TINYINT(1) NOT NULL DEFAULT 1
    COMMENT 'Every answer at the current level so far was clean (C)';
