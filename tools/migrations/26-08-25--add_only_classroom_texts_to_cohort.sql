-- Let a teacher restrict a class to the texts they share.
--
-- This behavior already existed as the `hide_recommendations` feature, but the
-- set of classes it applied to was a constant in the source
-- (zeeguu/core/user_feature_toggles.py), so enabling it for a class meant a
-- deploy. The column moves that decision to the teacher.
--
-- Cohort 564 is the class the constant named; the UPDATE below keeps it behaving
-- exactly as it does today, so the constant can be deleted in the same commit.

ALTER TABLE cohort
    ADD COLUMN only_classroom_texts BOOLEAN NOT NULL DEFAULT 0;

UPDATE cohort SET only_classroom_texts = 1 WHERE id = 564;
