-- The regional variety the audio lesson is READ in -- and, with it, a name for
-- the variety preference that already existed.
--
-- user_language.variety becomes user_language.feed_variety. It has always meant
-- "which country's sources", but it was the only variety preference there, so
-- bare was unambiguous. voice_variety arriving beside it ends that: an
-- unqualified `variety` would no longer say which question it answers. Renaming
-- it in the same migration means production never holds the ambiguous pair.
--
-- RUN THIS BEFORE DEPLOYING THE API, not after. The serializer behind
-- /get_user_details reads user_language.voice_variety for every row it returns,
-- so an API running ahead of this migration answers 500 to every user on every
-- request -- not only to users with a voice preference, and not only on the
-- audio-lesson path.
--
-- `user_language.voice_variety` is the learner's preference; the two `variety`
-- columns on the lesson tables record what a cached row was actually voiced in,
-- and are part of its cache key. Both lesson tables are shared across
-- ALL users, so without the variety in the key whoever generated a lesson first
-- would decide which accent every later learner hears.
--
-- No backfill, and none is needed. Every existing row was generated when nobody
-- could express a preference, and NULL is exactly what those rows mean: "voiced
-- without a variety". They go on being served to learners who ask for none, and
-- a learner who does ask misses them and gets one generated in their own accent.
--
-- voice_variety is kept apart from feed_variety on purpose: "Everywhere" is a
-- coherent answer to which country's news to read and an incoherent one to which
-- accent to be read in, and picking a Brazilian voice must not silently narrow
-- the feed to Brazilian sources.

ALTER TABLE user_language
CHANGE variety feed_variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the country this learner wants their feed from; NULL = everywhere';

ALTER TABLE user_language
ADD COLUMN voice_variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety audio lessons are read in; NULL = no preference';

ALTER TABLE audio_lesson_meaning
ADD COLUMN variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety this lesson was voiced in; NULL = voiced without a variety';

ALTER TABLE audio_lesson_dialogue
ADD COLUMN variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety this dialogue was voiced in; NULL = voiced without a variety';
