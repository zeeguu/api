import flask

from zeeguu_api.api import api
from zeeguu_api.api.utils.route_wrappers import cross_domain, with_session


@api.route("/is_feature_enabled/<feature_name>", methods=["GET"])
@cross_domain
@with_session
def is_feature_enabled(feature_name):

    func = _feature_map().get(feature_name, None)

    if not func:
        return "NO"

    if func(flask.g.user):
        return "YES"

    return "NO"


def _feature_map():
    return {"activity_dashboard": _activity_dashboard_enabled}


def _activity_dashboard_enabled(user):
    return user.id in [534, 2455, 2833]
