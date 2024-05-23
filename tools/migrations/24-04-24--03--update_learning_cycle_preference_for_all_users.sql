/* 
 Updates the learning cycle preference enabling productive exercises for all users.
 */
INSERT INTO user_preference (user_id, `key`, value)
SELECT u.id, 'productive_exercises', 'true'
FROM `user` AS u
WHERE u.id NOT IN (SELECT user_id FROM user_preference WHERE `key` = 'productive_exercises');
