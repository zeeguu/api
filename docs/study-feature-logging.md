# Study feature logging

What the logs answer, per learner and per day, about the features built for the
Danish learning challenge (classes 605, 607 and 609 on zeeguu.org), released
14 to 21 Nov 2026 (apps 1.3.20 to 1.3.22). For each feature: the question, where
the answer is, a query, and the caveats.

## How events get logged

Everything is in `user_activity_data` (`user_id, time, event, value,
extra_data, source_id, platform`) unless said otherwise. Two kinds of rows:

- **Client events**, uploaded by the web app through
  `/upload_user_activity_data`. The iOS and Android apps run the same web code
  (Capacitor), so a new or changed client event is on the web as soon as the
  web is deployed, but **on phones only from the next app release**. The
  client sends `time` in UTC.
- **Server events**, written by the API itself
  (`UserActivityData.log_server_event`). They are there **for every platform
  and every app build from the API deploy on**. `extra_data` is JSON. `time`
  is server time, which is UTC (container and MySQL are UTC).

`platform`: 1 web desktop, 2 web mobile, 3 iOS app, 4 Android app,
5 extension (`zeeguu/core/constants.py`). On server events it is the platform
of the login session, which logins only remember since 15 Nov 2026: on
24 Nov most of the study's sessions were older, so their server events have
`platform` NULL. Take the platform from the client events around them when
it matters.

The learners are in Denmark: a "day" is the Copenhagen day (UTC+1 until
29 Mar 2027). The queries below shift UTC with `CONVERT_TZ(t, '+00:00',
'+01:00')`; the streak itself uses the learner's own time zone.

The learners of the study:

```sql
SELECT cohort_id, user_id FROM user_cohort_map WHERE cohort_id IN (605, 607, 609);
```

## Event reference

| Event | Kind | value | extra_data |
|---|---|---|---|
| `STUDY_REMINDER_OPENED` | client, since 1.3.20 | reminder text id (`goal-v1`) | `{"scheduled_for", "test"}` |
| `STUDY_REMINDER_SCHEDULED` | client, **new** | reminder text id | `{"at": [UTC times]}`, `[]` when turned off |
| `PREFERENCE_CHANGED` | server, **new** | preference key | `{"from", "to"}`, plus `"cohort_id"` when a class set it |
| `DAILY_GOAL_REACHED` | server, **new** | language code | `{"goal_minutes", "streak"}` |
| `STREAK_BAR_TAPPED` | client, **new** | language code | `{"current", "practiced_today", "ms_to_streak", "streak"}` |
| `AUDIO_LESSON_SUBJECT_SET` | server, **new** | language code | `{"from": [type, subject], "to": [type, subject]}` |
| `EVERGREEN_LISTED` | server, **new** | `all`, `topic:<title>`, `keyword:<text>` | `{"shown": [ids], "new_today": [ids], "keyword_matches": {id: keyword}}` |
| `OPEN ARTICLE` | client; value **new** | where it was opened from (see below) | `UMR` |
| `KEYWORD_ADDED`, `KEYWORD_REMOVED` | server, **new** | the keyword | `{"search_id", "language_id"}` |
| `SUBSCRIBE_TO_SEARCH`, `UNSUBSCRIBE_FROM_SEARCH` | client, older | the keyword | `news` / `evergreen` / empty |
| `SHORT_TEXT_ADDED`, `SHORT_TEXT_OPENED`, `SHORT_TEXT_TRANSLATED` | server, **new** | short_text id | `{"language", "words"}` (`"instead_of"`, `"to"`); never the text |

`PREFERENCE_CHANGED` covers `study_reminder_enabled`, `study_reminder_time`,
`notifications_permission`, `daily_goal_minutes` and `audio_lesson_minutes`.
A first save shows `"from": null`.

## 1. Daily study reminder

**Who turned it on or off, and when.** `PREFERENCE_CHANGED` with value
`study_reminder_enabled` / `study_reminder_time`. `notifications_permission`
says whether the phone may show notifications at all (`granted`, `denied`,
`prompt`): a reminder that is on but not allowed never shows. The current state
is in `user_preference`. Before the API deploy only the current state exists
(`user_preference` keeps no history).

```sql
SELECT a.user_id, a.time, a.value AS setting,
  JSON_UNQUOTE(JSON_EXTRACT(a.extra_data, '$.from')) AS was,
  JSON_UNQUOTE(JSON_EXTRACT(a.extra_data, '$.to')) AS now
FROM user_activity_data a
JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
WHERE a.event = 'PREFERENCE_CHANGED'
  AND a.value IN ('study_reminder_enabled', 'study_reminder_time', 'notifications_permission')
ORDER BY a.user_id, a.time;
```

**Was a reminder sent on a given day.** The reminder is a local notification
the phone schedules for the next seven days at the chosen time, leaving out a
day once its goal is met; there is no server push, and iOS shows it without
running the app, so "shown" is never logged. What is logged is what the phone
scheduled: `STUDY_REMINDER_SCHEDULED`, each time the list of times changes (a
new day enters the week, the goal is met, the setting changes). A reminder was
due at time T if the last `STUDY_REMINDER_SCHEDULED` before T lists T, and it
was shown if the permission was `granted` then. A goal met on the web does not
remove the phone's reminder until the app is opened. A learner who does not
open the app for a week stops being reminded.

```sql
-- the last schedule before 19:00 (Copenhagen) on 2026-11-25, per learner
SELECT a.user_id, a.time AS scheduled_at, a.extra_data
FROM user_activity_data a
JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
WHERE a.event = 'STUDY_REMINDER_SCHEDULED'
  AND a.time = (SELECT MAX(b.time) FROM user_activity_data b
                WHERE b.user_id = a.user_id AND b.event = 'STUDY_REMINDER_SCHEDULED'
                  AND b.time < '2026-11-25 18:00:00');
-- then: is '2026-11-25T18:00:00.000Z' (or the learner's own time) in extra_data.at
```

**Did the person open the app from it, and how long after.**
`STUDY_REMINDER_OPENED`: `scheduled_for` is when the reminder was due (UTC),
`time` when it was tapped. `test: true` rows come from the developer tools.

```sql
SELECT o.user_id, o.due_utc, MIN(o.time) AS opened_utc,
  TIMESTAMPDIFF(MINUTE, STR_TO_DATE(LEFT(o.due_utc, 19), '%Y-%m-%dT%H:%i:%s'), MIN(o.time))
    AS minutes_after_due
FROM (
  SELECT a.user_id, a.time, JSON_UNQUOTE(JSON_EXTRACT(a.extra_data, '$.scheduled_for')) AS due_utc
  FROM user_activity_data a
  JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
  WHERE a.event = 'STUDY_REMINDER_OPENED' AND JSON_EXTRACT(a.extra_data, '$.test') = false
) o
GROUP BY o.user_id, o.due_utc
ORDER BY o.due_utc;
```

Caveats: Android apps up to 1.3.22 log one tap again on later app starts (on
prod, one reminder of user 7125 was logged as opened on three days). Group by
`scheduled_for` and take the first open, as above; from the next app release
the app logs each reminder once. `STUDY_REMINDER_SCHEDULED` arrives with the
next app release.

## 2. Daily goal and the ring around the flame

**On which days was the goal reached.** `DAILY_GOAL_REACHED`, written once per
day and language at the moment the day's study time reaches the goal (when the
streak counts the day). `goal_minutes` is the goal at that moment.

```sql
SELECT a.user_id, DATE(CONVERT_TZ(a.time, '+00:00', '+01:00')) AS day, a.value AS language,
  JSON_EXTRACT(a.extra_data, '$.goal_minutes') AS goal, JSON_EXTRACT(a.extra_data, '$.streak') AS streak,
  TIME(CONVERT_TZ(a.time, '+00:00', '+01:00')) AS reached_at
FROM user_activity_data a
JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
WHERE a.event = 'DAILY_GOAL_REACHED'
ORDER BY a.user_id, day;
```

Before the API deploy, reconstruct it from the session tables (durations are in
ms; a session counts for the day it was last active in). This adds up every
language and assumes the 10-minute goal, so it is an approximation:

```sql
SELECT t.user_id, t.day, ROUND(SUM(t.ms) / 60000, 1) AS minutes, SUM(t.ms) >= 600000 AS reached_10
FROM (
  SELECT user_id, DATE(CONVERT_TZ(last_action_time, '+00:00', '+01:00')) AS day, duration AS ms FROM user_reading_session
  UNION ALL SELECT user_id, DATE(CONVERT_TZ(last_action_time, '+00:00', '+01:00')), duration FROM user_exercise_session
  UNION ALL SELECT user_id, DATE(CONVERT_TZ(last_action_time, '+00:00', '+01:00')), duration FROM user_browsing_session
  UNION ALL SELECT user_id, DATE(CONVERT_TZ(last_action_time, '+00:00', '+01:00')), duration FROM user_listening_session
  UNION ALL SELECT user_id, DATE(CONVERT_TZ(last_action_time, '+00:00', '+01:00')), duration FROM user_watching_session
) t
JOIN user_cohort_map m ON m.user_id = t.user_id AND m.cohort_id IN (605, 607, 609)
WHERE t.day >= '2026-11-14'
GROUP BY t.user_id, t.day
ORDER BY t.user_id, t.day;
```

**Did the person see or tap the ring.** The ring is on the current language's
flame in the top bar of every page while the day's goal is not met, so a
learner who used the app before reaching the goal saw it; no event for
"seen". `STREAK_BAR_TAPPED` logs a tap on a language in the bar (on the current
language it opens the language list; on another it switches) with
`practiced_today` and `ms_to_streak`, so a tap while the ring was filling
shows as `practiced_today: false`. Arrives with the next app release; on the
web on deploy. The hover title with the minutes left is desktop only and not
logged.

**Changes to the goal.** `PREFERENCE_CHANGED` with value `daily_goal_minutes`.
A goal raised by joining a class with `cohort.daily_goal_minutes` carries
`cohort_id`. The class goal of 605, 607 and 609 is 10 minutes.

## 3. A0 audio lessons and learner tuning

Already logged and working (checked on prod, 24 Nov: 21 A0 lessons completed by
the study's learners since 14 Nov, 11 of them with answers).

- `daily_audio_lesson`: one row per lesson (`created_at`, `last_completed_at`,
  `listened_count`, `canonical_suggestion` = the situation, `next_situations`).
- `audio_lesson_dialogue.tuning` (through `daily_audio_lesson_segment`): the
  pace, repetition, length and minutes the lesson was written with.
- `audio_lesson_feedback`: one row per lesson and aspect (`pace`, `repetition`,
  `situation`; `length` only from apps before the length slider) with
  `created_at` and `updated_at`. A changed answer overwrites the row: the first
  answer is lost, the last one is kept.
- `user_listening_session`: listening time.

**Dismissed without answering** is not an event: the questions are inline on
the finished lesson's page, with nothing to dismiss. A completed A0 lesson
with no `audio_lesson_feedback` rows is a lesson the learner did not answer
about:

```sql
SELECT l.user_id, l.id AS lesson, l.canonical_suggestion, l.last_completed_at,
  (SELECT COUNT(*) FROM audio_lesson_feedback f WHERE f.daily_audio_lesson_id = l.id) AS answers,
  (SELECT GROUP_CONCAT(CONCAT(f.aspect, '=', f.value)) FROM audio_lesson_feedback f
    WHERE f.daily_audio_lesson_id = l.id) AS feedback
FROM daily_audio_lesson l
JOIN user_cohort_map m ON m.user_id = l.user_id AND m.cohort_id IN (605, 607, 609)
WHERE l.last_completed_at IS NOT NULL AND l.created_at >= '2026-11-14'
  AND EXISTS (SELECT 1 FROM daily_audio_lesson_segment s
              JOIN audio_lesson_dialogue d ON d.id = s.audio_lesson_dialogue_id
              WHERE s.daily_audio_lesson_id = l.id AND d.builds_on_history = 1)
ORDER BY l.user_id, l.id;
```

**The situation picker in the lesson settings.** `daily_audio_subscription`
keeps only the current subject. `AUDIO_LESSON_SUBJECT_SET` (server) logs each
change made there, with the subject before and after. A situation chosen after
a lesson is the `situation` row of `audio_lesson_feedback` instead. The lesson
length slider is `PREFERENCE_CHANGED` with value `audio_lesson_minutes`.

## 4. Evergreen tab

A0 learners do not get the tab (`NoFeedAtA0`); many of the study's learners are
A0.

**Tab opened, articles shown.** `EVERGREEN_LISTED` (server): one row per
listing, that is per visit to the tab and per pill or search picked in its
filter row, with the article ids shown. `evergreen_impression` has, per learner
and article, the first and last day it was shown and on how many days, which
is enough for "shown at all" back to 14 Nov but not for per-day counts.

**Opened from it.** `OPEN ARTICLE`'s value is where the article was opened
from: `evergreen`, `news`, `inbox`, `classroom`, `saved`, `history`,
`own_texts`, `share_sheet`, another page's first path segment
(`daily-audio`, `aiki`, `words`, ...), `share` or `deeplink` for a link into the
app, and `direct` when the app was opened on the article. A list filter is
added: `news:search`, `news:topic`, `evergreen:keyword`, `evergreen:search`.
Search now lives inside News and Evergreen, so "from Search" is the `:search`
suffix. Before the next app release, phones (and the web before its deploy)
send an empty value; the older `CLICKED ARTICLE` (News and News search only;
its `extra_data` feeds the News ranking) and `user_article.opened` remain.

`OPEN ARTICLE` has no article id column of its own; its `source_id` is the
article's `source_id`.

```sql
-- per learner and day: Evergreen listings, articles shown, opened from Evergreen
SELECT a.user_id, DATE(CONVERT_TZ(a.time, '+00:00', '+01:00')) AS day,
  SUM(a.event = 'EVERGREEN_LISTED') AS listings,
  SUM(CASE WHEN a.event = 'EVERGREEN_LISTED' THEN JSON_LENGTH(a.extra_data, '$.shown') END) AS shown,
  SUM(a.event = 'OPEN ARTICLE' AND a.value LIKE 'evergreen%') AS opened_from_evergreen,
  SUM(a.event = 'OPEN ARTICLE' AND a.value LIKE 'news%') AS opened_from_news,
  SUM(a.event = 'OPEN ARTICLE' AND a.value LIKE 'inbox%') AS opened_from_inbox
FROM user_activity_data a
JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
WHERE a.event IN ('EVERGREEN_LISTED', 'OPEN ARTICLE') AND a.time >= '2026-11-14'
GROUP BY a.user_id, day
ORDER BY a.user_id, day;

-- reading sessions with where their article was opened from
SELECT r.user_id, r.start_time, r.article_id, ROUND(r.duration / 60000, 1) AS minutes,
  (SELECT a.value FROM user_activity_data a JOIN article ar ON ar.source_id = a.source_id
    WHERE a.user_id = r.user_id AND a.event = 'OPEN ARTICLE' AND ar.id = r.article_id
      AND a.time BETWEEN r.start_time - INTERVAL 2 MINUTE AND r.start_time + INTERVAL 2 MINUTE
    ORDER BY a.time DESC LIMIT 1) AS opened_from
FROM user_reading_session r
JOIN user_cohort_map m ON m.user_id = r.user_id AND m.cohort_id IN (605, 607, 609)
WHERE r.start_time >= '2026-11-14'
ORDER BY r.user_id, r.start_time;
```

## 5. Keywords

The keywords are `search_subscription` rows (joined to `search.keywords`),
which have no dates. `KEYWORD_ADDED` / `KEYWORD_REMOVED` (server) log every
change made through the API, from any screen; the older client events
`SUBSCRIBE_TO_SEARCH` / `UNSUBSCRIBE_FROM_SEARCH` come only from News and
Evergreen, not from the interests settings. **Keywords a researcher adds
directly in the database leave no event**: note them (who, when, which) where
the study keeps its records, or add them through the API.

**Which recommended articles matched a keyword.** `EVERGREEN_LISTED`'s
`keyword_matches` maps each shown article that a keyword brought to that
keyword (the first one, when several match). The News feed does not say why it
recommended an article.

```sql
SELECT a.user_id, a.time, a.value AS filter,
  JSON_LENGTH(a.extra_data, '$.shown') AS shown,
  JSON_LENGTH(a.extra_data, '$.keyword_matches') AS from_keywords,
  JSON_EXTRACT(a.extra_data, '$.keyword_matches') AS matches
FROM user_activity_data a
JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
WHERE a.event = 'EVERGREEN_LISTED'
ORDER BY a.user_id, a.time;

-- current keywords
SELECT ss.user_id, GROUP_CONCAT(s.keywords SEPARATOR '; ') AS keywords
FROM search_subscription ss JOIN search s ON s.id = ss.search_id
JOIN user_cohort_map m ON m.user_id = ss.user_id AND m.cohort_id IN (605, 607, 609)
GROUP BY ss.user_id;
```

## 6. Inbox: shared texts and friends' shares

**Texts shared from other apps** (a WhatsApp message): `short_text` (the text,
shared between learners who bring the same one) and `user_short_text`
(`created_at`, `last_opened_at`; the row is deleted when the learner removes
the text, and with it these dates). `SHORT_TEXT_ADDED` (server) logs each text
brought in, `SHORT_TEXT_OPENED` each open in the text reader (bringing a text
in opens it, so an add is followed by an open), `SHORT_TEXT_TRANSLATED` a
whole-text translation. Words tapped in it are `TRANSLATE TEXT` / `SPEAK TEXT`
with `extra_data` `short_text` and the text's `source_id`, and bookmarks.

```sql
SELECT a.user_id, DATE(CONVERT_TZ(a.time, '+00:00', '+01:00')) AS day,
  SUM(a.event = 'SHORT_TEXT_ADDED') AS added, SUM(a.event = 'SHORT_TEXT_OPENED') AS opened,
  SUM(a.event = 'SHORT_TEXT_TRANSLATED') AS translated_whole
FROM user_activity_data a
JOIN user_cohort_map m ON m.user_id = a.user_id AND m.cohort_id IN (605, 607, 609)
WHERE a.event LIKE 'SHORT_TEXT_%'
GROUP BY a.user_id, day;
```

**Shares between friends**: `shared_article` (`from_user_id`, `to_user_id`,
`created_at` = received, `read_at` = opened, `dismissed_at`), already complete.
Opening one from Inbox is `OPEN ARTICLE` with value `inbox`.

```sql
SELECT sa.to_user_id, sa.from_user_id, sa.article_id, sa.created_at, sa.read_at, sa.dismissed_at
FROM shared_article sa
WHERE sa.to_user_id IN (SELECT user_id FROM user_cohort_map WHERE cohort_id IN (605, 607, 609))
   OR sa.from_user_id IN (SELECT user_id FROM user_cohort_map WHERE cohort_id IN (605, 607, 609));
```

On 24 Nov no learner of the study had a shared text or a friend's share.

## 7. Other things shipped since 9 Nov 2026

| Feature | Logged |
|---|---|
| Confetti and the feedback summary at the end of an audio lesson | the completion is `daily_audio_lesson.last_completed_at`; the summary follows from the answers |
| A0 situations in the lesson settings (emoji pills, More situations, Type your own) | `AUDIO_LESSON_SUBJECT_SET` (new); typed subjects are kept verbatim in `to` |
| Lesson length slider (1.3.22) | `PREFERENCE_CHANGED` `audio_lesson_minutes` (new); `tuning.minutes` on the lesson |
| Search inside News and Evergreen (the Search tab is gone) | `SEARCH QUERY` (client, existing); opens as `news:search` / `evergreen:search` (new) |
| Search snippets on result cards | not logged (a display change) |
| News shows only news; general articles go to Evergreen | follows from `article.article_type` |
| Guest signup with a class code joins the class | `user_cohort_map`; the class's goal as `PREFERENCE_CHANGED` with `cohort_id` (new) |
| Aiki unlock countdown | not covered here |
| Exercises and examples at the learner's level, dialogue lessons above A0 | content changes, no use to log |
| Toasts at the top, Settings back in the phone's More panel, BackArrow target, audio multiple choice shows a wrong pick | not logged (layout) |
