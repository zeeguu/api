import flask

from zeeguu.api.endpoints import api
from zeeguu.api.utils import cross_domain, json_result, requires_session
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


@api.route("/disabled_exercise_types", methods=["GET"])
@cross_domain
@requires_session
def get_disabled_exercise_types():
    """
    The exercise types the client should leave out of its sessions, for when
    one is broken and its fix is waiting for app review. Set in api.cfg, with
    the names in EXERCISE_TYPES in the web repo, and read at startup, so it
    takes a restart:

    DISABLED_EXERCISE_TYPES = ["Match_three_L1W_to_three_L2W"]
    """
    return json_result(flask.current_app.config.get("DISABLED_EXERCISE_TYPES", []))


# Re-export for backward compatibility
__all__ = ["features_for_user", "is_feature_enabled_for_user"]
