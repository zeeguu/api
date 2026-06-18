/*
  Add article.crawled_at — the ingestion timestamp.

  Why
  ---
  `article` only had `published_time`, which is the SOURCE's publish date and can
  be backdated. There was no record of when WE actually crawled/inserted a row,
  so crawler-throughput metrics ("articles ingested per hour per language") were
  impossible — only a stale snapshot via feed.last_crawled_time. crawled_at fills
  that gap and is the natural basis for the crawler dashboard / report digest.

  Existing rows
  -------------
  Left NULL on purpose: we genuinely don't know when historical rows were
  ingested, and stamping all ~4.6M of them at migration time would put a fake
  day-0 spike into every rate chart. New rows auto-stamp via the DEFAULT below;
  queries just treat NULL as "before we started tracking".

  MySQL 5.7 notes
  ---------------
  - This server has no INSTANT ADD COLUMN (that's 8.0.12+), so each ALTER below
    reorganizes the table. LOCK=NONE keeps crawl/live writes flowing, but on
    ~4.6M rows it takes a few minutes and temp disk — run it in a low-traffic
    window.
  - Step 2 only attaches a DEFAULT; defaults apply to new inserts only, so the
    existing NULLs are left untouched.

  Ordering: run this BEFORE deploying the model change — the ORM maps crawled_at,
  so it must exist on the table first.
*/

ALTER TABLE article
    ADD COLUMN crawled_at DATETIME NULL,
    ALGORITHM=INPLACE, LOCK=NONE;

ALTER TABLE article
    MODIFY crawled_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP;
