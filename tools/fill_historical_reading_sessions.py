from zeeguu_core.model.user_activitiy_data import UserActivityData
from zeeguu_core.model.user_reading_session import UserReadingSession

import zeeguu_core
from datetime import datetime

'''
    Script that loops through all the exeuser_activity_data actions in the database, and recomputes the history of
    reading sessions.

    NOTE: It deletes and recreates the table
'''
# List of excluded ids that could not be recreated
EXCLUDED_IDS = [13787, 14215, 14217, 14218, 14222, 14223, 14224, 14225, 14226, 14227, 14228, 14229, \
                14230, 14231, 14232, 14233, 14234, 14235, 14236, 14237, 14238, 14239, 14240, 14241, \
                14242, 14243, 14244, 14245, 14246, 14247, 14248, 14249, 14250, 20108, 20109]

db_session = zeeguu_core.db.session

# Clear table before starting
UserReadingSession.query.delete()
db_session.commit()

all_data = UserActivityData.find()
data = [each for each in all_data if each.id > 77420]

count = 0

for user_action in data:
    # Special case that causes a DB exception because of non supported symbols from the article
    if user_action.id not in EXCLUDED_IDS:

        # NOTE: Not all scenarios include the url
        user = user_action.user_id
        time = user_action.time

        try:
            UserReadingSession.update_reading_session(db_session,
                                                      user_action.event,
                                                      user,
                                                      user_action.get_article_id(db_session),
                                                      current_time=time
                                                      )
            count += 1
            print(str(count) + " " + str(datetime.now()) + " " + str(user_action.id))
        except Exception as e:
            print(f"caught exception for {user_action.id} ...")
            import traceback

            print(traceback.format_exc())
            db_session.rollback()
