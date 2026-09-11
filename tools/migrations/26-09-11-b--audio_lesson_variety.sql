-- The regional variety the audio lesson is READ in, and a name for each of the
-- two preferences that now sit side by side.
--
-- They answer different questions, so neither can be the bare `variety` the row
-- used to carry:
--
--   feed_variety  "show me news from Belgium"  -- a filter over sources
--   dialect       "I am learning Flemish"      -- what the learner is studying
--
-- The second is deliberately not called voice_variety. The voice is the first
-- consumer to honour it, not the only one: the translator's target and what the
-- LLM is told to write in are the same question asked by other features, and a
-- column named for the voice would be the wrong place for them to read.
--
-- RUN THIS BEFORE DEPLOYING THE API, not after. The serializer behind
-- /get_user_details reads user_language.dialect for every row it returns,
-- so an API running ahead of this migration answers 500 to every user on every
-- request -- not only to users with a voice preference, and not only on the
-- audio-lesson path.
--
-- `user_language.dialect` is the learner's preference; the two `variety` columns
-- on the lesson tables record what a cached row was actually voiced in, and are
-- part of its cache key. Both lesson tables are shared across
-- ALL users, so without the variety in the key whoever generated a lesson first
-- would decide which accent every later learner hears.
--
-- No backfill, and none is needed. Every existing row was generated when nobody
-- could express a preference, and NULL is exactly what those rows mean: "voiced
-- without a variety". They go on being served to learners who ask for none, and
-- a learner who does ask misses them and gets one generated in their own accent.
--
-- dialect is kept apart from feed_variety on purpose: "Everywhere" is a coherent
-- answer to which country's news to read and an incoherent one to which dialect
-- you are learning, and choosing to be read to in Brazilian must not silently
-- narrow the feed to Brazilian sources.

ALTER TABLE user_language
CHANGE variety feed_variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the country this learner wants their feed from; NULL = everywhere';

ALTER TABLE user_language
ADD COLUMN dialect VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety of this language the learner is studying; NULL = no preference';

ALTER TABLE audio_lesson_meaning
ADD COLUMN variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety this lesson was voiced in; NULL = voiced without a variety';

ALTER TABLE audio_lesson_dialogue
ADD COLUMN variety VARCHAR(2) DEFAULT NULL
COMMENT 'ISO 3166-1 alpha-2 of the variety this dialogue was voiced in; NULL = voiced without a variety';
