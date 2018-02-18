from datetime import datetime

import flask
from flask import request
import zeeguu

from . import api
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from zeeguu.model import UserActivityData

db = zeeguu.db

@api.route("/upload_user_activity_data", methods=["POST"])
@cross_domain
@with_session
def upload_user_activity_data():
    """
    The user needs to be logged in, so the event
    referst to themselves. Thus there is no need
    for submitting a user id.

    There are four elements that can be submitted for
    an user activity event. Within an example they are:

            time: '2016-05-05T10:11:12',
            event: "User Read Article",
            value: "300s",
            extra_data: "{article_source: 2, ...}"

    All these four elements have to be submitted as POST
    arguments

    :param self:
    :return: OK if all went well
    """

    time = request.form['time']
    event = request.form['event']
    value = request.form['value']
    extra_data = request.form['extra_data']

    zeeguu.log(f'{event} {value} {extra_data}')

    new_entry = UserActivityData(flask.g.user,
                                 datetime.strptime(time, "%Y-%m-%dT%H:%M:%S"),
                                 event,
                                 value,
                                 extra_data)
    db.session.add(new_entry)
    db.session.commit()
    return "OK"


@api.route("/test_upload_user_activity_data", methods=["POST"])
@cross_domain
@with_session
def test_upload_user_activity_data():
    """
    The user needs to be logged in, so the event
    referst to themselves. Thus there is no need
    for submitting a user id.

    There are four elements that can be submitted for
    an user activity event. Within an example they are:

            time: '2016-05-05T10:11:12',
            event: "User Read Article",
            value: "300s",
            extra_data: "{article_source: 2, ...}"

    All these four elements have to be submitted as POST
    arguments

    :param self:
    :return: OK if all went well
    """

    time = request.form['time']
    event = request.form['event']
    value = request.form['value']
    extra_data = request.form['extra_data']

    new_entry = UserActivityData(flask.g.user,
                                 datetime.strptime(time, "%Y-%m-%dT%H:%M:%S"),
                                 event,
                                 value,
                                 extra_data)
    db.session.add(new_entry)
    db.session.commit()
    return json_result(new_entry.data_as_dictionary())
