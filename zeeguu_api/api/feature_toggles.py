import flask

from zeeguu_api.api import api
from zeeguu_api.api.utils.route_wrappers import cross_domain, with_session


feature_map = {"activity_dashboard": [534, 2455, 2833]}


@api.route("/is_feature_enabled/<feature_name>", methods=["POST"])
@cross_domain
@with_session
def is_feature_enabled(feature_name):

    if int(flask.g.user.id) in feature_map.get(feature_name, None):
        return str("YES")

    return "NO"
