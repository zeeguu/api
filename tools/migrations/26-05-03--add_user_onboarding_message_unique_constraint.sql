-- Add unique constraint to ensure one record per user/message
ALTER TABLE `zeeguu_test`.`user_onboarding_message`
ADD UNIQUE INDEX `ux_user_onboarding_message_user_message` (`user_id`, `onboarding_message_id`);
