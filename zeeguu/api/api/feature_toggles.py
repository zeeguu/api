import flask

from zeeguu.api.api import api
from zeeguu.api.api.utils.route_wrappers import cross_domain, with_session


@api.route("/is_feature_enabled/<feature_name>", methods=["GET"])
@cross_domain
@with_session
def is_feature_enabled(feature_name):

    """
    e.g.
    /is_feature_enabled/ems_teacher_dashboard

    will return YES or NO
    """

    func = _feature_map().get(feature_name, None)

    if not func:
        return "NO"

    if func(flask.g.user):
        return "YES"

    return "NO"


def _feature_map():
    return {
        "activity_dashboard": _activity_dashboard_enabled,
        "ems_teacher_dashboard": _ems_teacher_dashboard_enabled,
        "audio_exercises": _audio_exercises,
    }


def _audio_exercises(user):

    return user.id in [3148, 3149, 534]  # jk  # gn


def _ems_teacher_dashboard_enabled(user):
    ids_included = [
        2308,
        2671,
        534,
        2794,
        2673,
        2643,
        1862,
        1862,
        1865,
        2126,
        1863,
        2383,
        2970,
        2690,
        491,
        2820,
        2705,
        2819,
        2784,
    ]
    return user.id in ids_included


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
    ]
    return user.id not in ids_excluded_in_marias_experiment
