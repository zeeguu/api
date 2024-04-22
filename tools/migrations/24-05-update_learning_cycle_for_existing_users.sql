/* 
 Updates the learning cycle column to receptive for scheduled and learned bookmarks.
 */
UPDATE bookmark b SET learning_cycle = 1
WHERE b.id in (SELECT bookmark_id FROM basic_sr_schedule) -- bookmarks that are scheduled
OR b.learned = 1; -- bookmarks that are learned