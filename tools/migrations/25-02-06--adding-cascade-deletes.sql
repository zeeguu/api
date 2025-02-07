
ALTER TABLE zeeguu_test.topic_subscription DROP FOREIGN KEY topic_subscription_ibfk_1;
ALTER TABLE zeeguu_test.topic_subscription ADD CONSTRAINT topic_subscription_ibfk_1 FOREIGN KEY (user_id) REFERENCES zeeguu_test.`user`(id) ON DELETE CASCADE ON UPDATE RESTRICT;

ALTER TABLE zeeguu_test.user_feedback DROP FOREIGN KEY user_feedback_ibfk_1;
ALTER TABLE zeeguu_test.user_feedback ADD CONSTRAINT user_feedback_ibfk_1 FOREIGN KEY (user_id) REFERENCES zeeguu_test.`user`(id) ON DELETE CASCADE ON UPDATE RESTRICT;

ALTER TABLE zeeguu_test.bookmark_exercise_mapping DROP FOREIGN KEY bookmark_exercise_mapping_ibfk_1;
ALTER TABLE zeeguu_test.bookmark_exercise_mapping ADD CONSTRAINT bookmark_exercise_mapping_ibfk_1 FOREIGN KEY (exercise_id) REFERENCES zeeguu_test.exercise(id) ON DELETE CASCADE ON UPDATE RESTRICT;

ALTER TABLE zeeguu_test.user_notification DROP FOREIGN KEY user_notification_ibfk_1;
ALTER TABLE zeeguu_test.user_notification ADD CONSTRAINT user_notification_ibfk_1 FOREIGN KEY (user_id) REFERENCES zeeguu_test.`user`(id) ON DELETE CASCADE ON UPDATE RESTRICT;

DELETE
from bookmark_exercise_mapping
WHERE bookmark_id not in (SELECT id from bookmark);

ALTER TABLE zeeguu_test.bookmark_exercise_mapping ADD CONSTRAINT bookmark_exercise_mapping_bookmark_FK FOREIGN KEY (bookmark_id) REFERENCES zeeguu_test.bookmark(id) ON DELETE CASCADE ON UPDATE RESTRICT;
