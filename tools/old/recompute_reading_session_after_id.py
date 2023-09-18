from zeeguu.core.model.user_activitiy_data import UserActivityData
from zeeguu.core.model.user_reading_session import UserReadingSession

import zeeguu.core

"""
    Script that recomputes reading sessions after a certain UserActivityData ID 

"""
db_session = zeeguu.core.model.db.session

STARTING_ID = 1048627

user_actions = UserActivityData.query.filter(UserActivityData.id > STARTING_ID).all()
starting_time = user_actions[0].time


recent_reading_sessoins = UserReadingSession.query.filter(
    UserReadingSession.start_time > starting_time
).all()

for each in recent_reading_sessoins:
    if each.user.name not in ["Frida Beck-Larsen", "Mircea Lungu", "Emma"]:
        print(
            f"{each.id}, {each.start_time}, {each.user.name}, {each.user.email}, {each.article.id}, {each.duration/1000/60}"
        )
    db_session.delete(each)

db_session.commit()


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

recent_reading_sessoins = UserReadingSession.query.filter(
    UserReadingSession.start_time > starting_time
).all()

for each in recent_reading_sessoins:
    if each.user.name not in ["Frida Beck-Larsen", "Mircea Lungu", "Emma"]:
        print(
            f"{each.id}, {each.start_time}, {each.user.name}, {each.user.email}, {each.article.id}, {each.duration/1000/60}"
        )
