from time import sleep
from zeeguu.core.model import UserActivityData
import zeeguu.core

db_session = zeeguu.core.db.session

most_recent_events = UserActivityData.query.order_by(UserActivityData.id.desc()).limit(
    20
)


def print_event(each):
    print(
        f"[{each.time}] {each.user.name}, {each.event}, {each.value}, {each.extra_data}"
    )


for each in reversed(list(most_recent_events)):
    print_event(each)

most_recent_id = most_recent_events[0].id
most_recent_object = most_recent_events[0]

while True:
    db_session.commit()
    query = UserActivityData.query.filter(UserActivityData.id > most_recent_id)

    new_events = query.all()
    for each in new_events:
        print_event(each)
    if len(new_events) > 0:
        most_recent_id = new_events[-1].id
        most_recent_object = new_events[-1]
    sleep(1)
