import flask

from zeeguu.api.endpoints import api
from zeeguu.api.utils import cross_domain, with_session


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


def features_for_user(user):
    features = []
    for name, detector_function in _feature_map().items():
        if detector_function(user):
            features.append(name)
    return features


def _feature_map():
    return {
        "audio_exercises": _audio_exercises,
        "extension_experiment_1": _extension_experiment_1,
        "no_audio_exercises": _no_audio_exercises,
        "tiago_exercises": _tiago_exercises,
        "merle_exercises": _merle_exercises,
    }


def _tiago_exercises(user):
    right_user = user.invitation_code == "Tiago" or user.id == 534 or user.id == 4022
    right_language = user.learned_language.code in ["da"]
    print(right_language)
    print(right_user)
    return right_user and right_language


def _merle_exercises(user):
    right_user = (
        user.invitation_code == "Merle"
        or user.invitation_code == "MerleITU"
        or user.invitation_code == "PTCT"
        or user.id in [534, 2953, 4022, 4089, 4192]
    )
    return right_user


def _no_audio_exercises(user):
    return user.cohort and user.cohort.id == 447


def _audio_exercises(user):
    return user.cohort and user.cohort.id == 444


def _extension_experiment_1(user):
    return (
        (user.cohort and user.cohort.id == 437)
        or user.id in [3372, 3373, 2953, 3427, 2705]
        or user.id > 3555
    )
