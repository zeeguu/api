-- user_word.user_preference -> study_choice + unfit_reason (roadmap 0b).
-- user_preference itself stays, unused, until a later migration drops it.
-- After this, run tools/recompute_fit_after_study_choice.py for the words
-- that lose their forced "use in exercises" (step 3).

ALTER TABLE user_word
    ADD COLUMN study_choice ENUM('study','skip','known') NULL DEFAULT NULL,
    ADD COLUMN unfit_reason ENUM('rare_for_beginner','same_as_translation','too_short',
        'too_many_words','arbitrary_multi_word','bad_contexts','separated_mwe',
        'validator_gave_up','no_usable_context',
        'validator_invalid','replaced_by_fix','duplicate_meaning') NULL DEFAULT NULL;

-- 1. The learner's skips and "I know this"
UPDATE user_word SET study_choice = 'skip' WHERE user_preference = '-1';
UPDATE user_word SET study_choice = 'known' WHERE user_preference IN ('-6', '-4', '-2');

-- 2. -100: #896's write on the old word of a validator fix, else a learner's
-- "bad translation", which stays out as a skip until reports exist
UPDATE user_word uw
SET uw.unfit_reason = 'replaced_by_fix'
WHERE uw.user_preference = '-100'
  AND EXISTS (SELECT 1 FROM validation_log v
              WHERE v.action = 'fixed' AND v.user_word_id = uw.id AND v.meaning_id = uw.meaning_id);
UPDATE user_word SET study_choice = 'skip' WHERE user_preference = '-100' AND unfit_reason IS NULL;

-- 3. 1 is the learner's "study", except the opt-ins #895's bug forced on the
-- target of a validator fix with no sign of the learner choosing it: no star,
-- not added by them, no "set to study" event (roadmap item 0)
UPDATE user_word uw
JOIN meaning m ON m.id = uw.meaning_id
JOIN phrase p ON p.id = m.origin_id
SET uw.study_choice = 'study'
WHERE uw.user_preference = '1'
  AND NOT (
      uw.is_user_added = 0
      AND EXISTS (SELECT 1 FROM validation_log v
                  WHERE v.action = 'fixed' AND v.new_meaning_id = uw.meaning_id)
      AND NOT EXISTS (SELECT 1 FROM bookmark b
                      WHERE b.user_word_id = uw.id
                        AND (b.starred = 1 OR b.translation_source = 'user_added'))
      AND NOT EXISTS (SELECT 1 FROM user_activity_data a
                      WHERE a.user_id = uw.user_id
                        AND a.event = 'USER SET WORD TO STUDY'
                        AND a.value = p.content)
  );

-- 4. Words the validator found wrong with no correction: a sticky verdict.
-- Other unfit words get their reason the next time they are recomputed.
UPDATE user_word uw
SET uw.unfit_reason = 'validator_invalid'
WHERE uw.fit_for_study = 0
  AND uw.unfit_reason IS NULL
  AND EXISTS (SELECT 1 FROM validation_log v
              WHERE v.action = 'invalid' AND v.user_word_id = uw.id AND v.meaning_id = uw.meaning_id);
