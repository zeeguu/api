from time import sleep
from zeeguu.core.model import UserActivityData
import zeeguu.core
import timeago

db_session = zeeguu.core.db.session

most_recent_events = UserActivityData.query.order_by(UserActivityData.id.desc()).limit(
    20
)

from datetime import datetime
import time

def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset


def print_event(each):

    now = datetime.now()
    converted_time = datetime_from_utc_to_local(each.time)
    tago = timeago.format(converted_time, now)
    print(
        f"{tago:>18} {each.user.name:>15}  {each.event:<30} {each.value:<30} {each.extra_data}"
    )


for each in reversed(list(most_recent_events)):
    print_event(each)

most_recent_id = most_recent_events[0].id
most_recent_object = most_recent_events[0]

print(f"Looking for events after: {most_recent_id}")

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
