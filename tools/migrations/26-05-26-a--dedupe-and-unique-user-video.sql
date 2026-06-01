-- Fix: user_video never had a real UNIQUE(user_id, video_id) constraint. The model declared it
-- as a bare `db.UniqueConstraint(...)` expression (a no-op outside __table_args__), so no DDL was
-- ever emitted. As a result, concurrent first-open requests (/user_video + /video_opened fire
-- together on reader load) both INSERTed a row, producing duplicates -- after which
-- UserVideo.find / find_or_create (which used .one()) 500'd with MultipleResultsFound.
--
-- Dedupe existing rows (keep the lowest id per user+video), then add the missing unique key so
-- the race never recurs (the find_or_create rollback-and-requery handler now actually fires).
--
-- Note on cost: with no index yet on (user_id, video_id), the DELETE...JOIN below does a full
-- scan and GROUP BY on user_video, and the ALTER TABLE that follows rewrites the table to add
-- the unique key. For large tables (>1M rows) this will lock the table for a noticeable window
-- -- prefer to run during a maintenance window or off-peak.

DELETE uv FROM user_video uv
JOIN (
    SELECT user_id, video_id, MIN(id) AS keep_id
    FROM user_video
    GROUP BY user_id, video_id
    HAVING COUNT(*) > 1
) d ON uv.user_id = d.user_id
   AND uv.video_id = d.video_id
   AND uv.id <> d.keep_id;

ALTER TABLE user_video
    ADD UNIQUE KEY uq_user_video_user_video (user_id, video_id);
