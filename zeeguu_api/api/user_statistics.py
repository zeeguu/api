import flask

from zeeguu_api.api.utils.json_result import json_result
from zeeguu_core.user_statistics.activity import activity_duration_by_day
from . import api
from .utils.route_wrappers import cross_domain, with_session


@api.route("/bookmark_counts_by_date", methods=("GET",))
@cross_domain
@with_session
def bookmark_counts_by_date():
    """
    Words that have been translated in texts
    """
    return flask.g.user.bookmark_counts_by_date()


@api.route("/activity_by_day", methods=("GET",))
@cross_domain
@with_session
def activity_by_day():
    """
    User sessions by day
    """

    return json_result(activity_duration_by_day(flask.g.user))
