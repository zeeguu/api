-- Feed items the crawler rejected without saving an article, so the next
-- crawl skips them instead of downloading them and asking the LLM again.
--
-- Since api#881 a paywall over the daily sample quota leaves no article
-- behind, so Article.find(url) never finds it and every hourly crawl sent it
-- to the LLM again while it stayed in the feed: on 2026-10-19, 115 LLM calls
-- for 23 URLs.
--
-- content_simhash catches the same text under a new url (outlets rename the
-- slug when they edit the headline); it is compared within a feed over the
-- crawler's SIMHASH_LOOKBACK_DAYS. A new table, so no rebuild of anything big.

CREATE TABLE skipped_url (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url_id INT NOT NULL,
    feed_id INT NULL,
    content_simhash BIGINT UNSIGNED NULL,
    reason VARCHAR(42) NOT NULL,
    skipped_at DATETIME NOT NULL,

    UNIQUE KEY uq_skipped_url_url (url_id),
    KEY ix_skipped_url_feed_time (feed_id, skipped_at),
    FOREIGN KEY (url_id) REFERENCES url(id) ON DELETE CASCADE,
    FOREIGN KEY (feed_id) REFERENCES feed(id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4;
