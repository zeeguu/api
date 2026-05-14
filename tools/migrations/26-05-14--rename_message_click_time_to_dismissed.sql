-- The 26-05-03 migration that created `user_onboarding_message` is already
-- on master and has run on production. Editing that file in place to rename
-- the column does nothing on databases that have already applied it. This
-- forward migration performs the actual rename via ALTER TABLE.

ALTER TABLE user_onboarding_message
  CHANGE COLUMN message_click_time message_dismissed_time DATETIME NULL;
