/*
  Add retention_class to feed for the perennial-vs-ephemeral article pruning
  strategy (see zeeguu/docs/future-work/article-retention-perennial-vs-ephemeral.md).

  - 'perennial'  → evergreen content (science, history, culture). Kept long.
  - 'ephemeral'  → daily news, sports recaps, etc. Pruned aggressively.
  - 'unknown'    → not yet classified. Conservative retention window (default).

  All existing feeds default to 'unknown'; they will be tagged manually
  in a follow-up step.
*/

ALTER TABLE feed
  ADD COLUMN retention_class ENUM('perennial','ephemeral','unknown')
    NOT NULL DEFAULT 'unknown'
    AFTER feed_type;
