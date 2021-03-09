import json
from datetime import datetime

import flask
from flask import request
import zeeguu_core
from . import api, db_session
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from zeeguu_core.model import WatchInteractionEvent, WatchEventType


@api.route("/upload_smartwatch_events", methods=["POST"])
@cross_domain
@with_session
def upload_smartwatch_events():
    """
    This expects a post parameter named

        events

    which is a json array of dictionaries of the form:

        dict (
                bookmark_id: 1,
                time: 'YYYY-MM-DDTHH:MM:SS',
                event: "Glance"
            }

    :return: OK or FAIL
    """

    events = json.loads(request.form["events"])
    for event in events:
        event_type = WatchEventType.find_by_name(event["event"])
        if not event_type:
            event_type = WatchEventType(event["event"])
            db_session.add(event_type)
            db_session.commit()

        new_event = WatchInteractionEvent(
            event_type,
            event["bookmark_id"],
            datetime.strptime(event["time"], "%Y-%m-%dT%H:%M:%S"),
        )
        db_session.add(new_event)
    db_session.commit()

    return "OK"


# This seems to be broken; the corresponding test does not work.
@api.route("/get_smartwatch_events", methods=["GET"])
@cross_domain
@with_session
def get_smartwatch_events():
    """
    Returns an array of entries which are dicts:
        dict (
                bookmark_id: 1,
                time: 'YYYY-MM-DDTHH:MM:SS',
                event: "Glance"
            }

    :return: OK or FAIL
    """
    event_objects = WatchInteractionEvent.events_for_user(flask.g.user)
    sorted_events = sorted(event_objects, key=lambda event: event.time)
    events = [x.data_as_dictionary() for x in sorted_events]

    return json_result(events)
