from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.user import User
from zeeguu.core.model.user_reading_session import UserReadingSession

import zeeguu.core
from zeeguu.api.app import create_app
from datetime import datetime


app = create_app()
app.app_context().push()
"""
    Script that recomputes reading sessions after a certain UserActivityData ID 

"""
db_session = zeeguu.core.model.db.session

STARTING_ID = 1553032
END_ID = 1581172

user_actions = (
    UserActivityData.query.filter(UserActivityData.id > STARTING_ID)
    .filter(UserActivityData.id <= END_ID)
    .filter(UserActivityData.extra_data == "EXTENSION")
    .join(User)
    .filter(User.is_dev == 0)
    .all()
)
starting_time = user_actions[0].time


old_recent_reading_sessions = UserReadingSession.query.filter(
    UserReadingSession.start_time > starting_time
).all()
old_recent_reading_sessions_dict = {s.id: s for s in old_recent_reading_sessions}

count = 0
for user_action in user_actions:

    user_id = user_action.user_id
    time = user_action.time

    try:
        UserReadingSession.update_reading_session(
            db_session,
            user_action.event,
            user_id,
            user_action.get_article_id(db_session),
            current_time=time,
        )
        count += 1
        print(f"{count}/{len(user_actions)}")
    except Exception as e:
        print(f"caught exception for {user_action.id} ...")
        import traceback

        print(traceback.format_exc())
        db_session.rollback()


print("after recreation...")

new_recent_reading_sessions = UserReadingSession.query.filter(
    UserReadingSession.start_time > starting_time
).all()
new_recent_reading_sessions_dict = {s.id: s for s in new_recent_reading_sessions}

counter = 0
for s_id, s in new_recent_reading_sessions_dict.items():
    if s_id not in old_recent_reading_sessions_dict:
        counter += 1
        print(
            f"NEW!! {s.id}, {s.start_time}, {s.user.name}, {s.user.email}, {s.article.id}, {s.duration/1000/60}"
        )
        continue
    before = old_recent_reading_sessions_dict[s_id]
    after = s
    if s.duration != before.duration:
        counter += 1
        dif = abs(s.duration - before.duration)
        print(
            f"UPDATE NEW: {s.id}, {s.start_time}, {s.user.name}, {s.user.email}, {s.article.id}, {after.duration/1000/60}"
        )
        print(
            f"UPDATE OLD: {s.id}, {s.start_time}, {s.user.name}, {s.user.email}, {s.article.id}, {before.duration/1000/60}"
        )
        print(f"Diference is: {dif:.2f}")

print(f"Total rows affected: {counter}")
