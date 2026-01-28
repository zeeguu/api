import flask

from zeeguu.api.endpoints import api
from zeeguu.api.utils import cross_domain, requires_session
from zeeguu.core.model import User
from zeeguu.core.user_feature_toggles import (
    features_for_user,
    is_feature_enabled_for_user,
)


@api.route("/is_feature_enabled/<feature_name>", methods=["GET"])
@cross_domain
@requires_session
def is_feature_enabled(feature_name):
    """
    e.g.
    /is_feature_enabled/ems_teacher_dashboard

    will return YES or NO
    """
    user = User.find_by_id(flask.g.user_id)
    if is_feature_enabled_for_user(feature_name, user):
        return "YES"

    return "NO"


# Re-export for backward compatibility
__all__ = ["features_for_user", "is_feature_enabled_for_user"]
