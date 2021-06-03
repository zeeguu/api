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
    ids_excluded_in_marias_experiment = [
        2052,
        2133,
        2042,
        2652,
        2616,
        2650,
        2612,
        2574,
        2568,
        2598,
        534,
    ]
    return user.id not in ids_excluded_in_marias_experiment
