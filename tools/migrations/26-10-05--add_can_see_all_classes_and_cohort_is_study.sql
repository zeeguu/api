-- is_dev used to do two jobs: mark an account as the team's own (left out of
-- statistics) and let it open every class in the teacher dashboard. The second
-- is a privilege over all students' data, and 158 accounts had it, thesis
-- students and usability-test accounts among them. It gets its own column,
-- granted by hand to the few people who support teachers.
ALTER TABLE user
ADD COLUMN can_see_all_classes TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'Opens every class in the teacher dashboard, to support teachers';

-- A study, beta test or usability test run through a cohort. Its members are
-- real learners, but it is not a classroom, so it does not make its owner a
-- teacher in the public numbers (zeeguu.core.user_statistics.platform_totals).
ALTER TABLE cohort
ADD COLUMN is_study TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'A study or test group rather than a classroom';
