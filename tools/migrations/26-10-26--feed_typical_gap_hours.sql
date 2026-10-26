-- Average hours between a feed's articles, measured nightly by
-- tools/update_feed_typical_gaps.py; scales the stale-feed alert and the
-- ephemeral pruning window (zeeguu/core/feed_cadence.py). NULL = not measured.
ALTER TABLE feed
    ADD COLUMN typical_gap_hours FLOAT NULL DEFAULT NULL;
