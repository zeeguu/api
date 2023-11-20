from time import sleep
from zeeguu.core.model import UserActivityData

import timeago
from datetime import datetime
import time

import zeeguu.cl

db_session = zeeguu.core.model.db.session

EVENTS_COUNT = 24
SECONDS_BETWEEN_REFRESH = 5


def most_recent_events():
    return UserActivityData.query.order_by(UserActivityData.id.desc()).limit(
        EVENTS_COUNT
    )


def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(
        now_timestamp
    )
    return utc_datetime + offset


def print_event(each):
    now = datetime.now()
    converted_time = datetime_from_utc_to_local(each.time)
    tago = timeago.format(converted_time, now)
    print(
        f"{tago:>16} {str(converted_time):>28} {each.user.name:>20}  {each.event:<30} {each.article_id} {each.value:<30} {each.extra_data}"
    )


while True:
    import os

    db_session.commit()
    os.system("cls" if os.name == "nt" else "clear")
    # print(chr(27) + "[2J")

    print(f"Most recent {EVENTS_COUNT} user activity events")
    print(f"Refreshed every {SECONDS_BETWEEN_REFRESH} seconds")

    for each in reversed(list(most_recent_events())):
        print_event(each)

    sleep(SECONDS_BETWEEN_REFRESH)
