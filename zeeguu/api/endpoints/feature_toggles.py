import flask

from zeeguu.api.endpoints import api
from zeeguu.api.utils import cross_domain, requires_session
from zeeguu.core.model import User


@api.route("/is_feature_enabled/<feature_name>", methods=["GET"])
@cross_domain
@requires_session
def is_feature_enabled(feature_name):
    """
    e.g.
    /is_feature_enabled/ems_teacher_dashboard

    will return YES or NO
    """

    func = _feature_map().get(feature_name, None)

    if not func:
        return "NO"
    user = User.find_by_id(flask.g.user_id)
    if func(user):
        return "YES"

    return "NO"


def features_for_user(user):
    features = []
    for name, detector_function in _feature_map().items():
        if detector_function(user):
            features.append(name)
    return features


"""
    We have a code 'zeeguu-preview' which is used to invite
    general users and should give access to the latest feature set
    of Zeeguu. It can be used for usability tests and can be also
    spread by word of mouth to new participants.
"""
def is_feature_enabled_for_user(feature_name, user):
    return feature_name in features_for_user(user)

def _feature_map():
    return {
        "audio_exercises": _audio_exercises,
        "extension_experiment_1": _extension_experiment_1,
        "no_audio_exercises": _no_audio_exercises,
        "tiago_exercises": _tiago_exercises,
        "new_topics": _new_topics,
        "merle_exercises": _merle_exercises,
        "exercise_levels": _exercise_levels,
    }


def _new_topics(user):
    return True


def _tiago_exercises(user):
    right_user = user.invitation_code == "Tiago" or user.id == 534 or user.id == 4022
    right_language = user.learned_language.code in ["da"]
    return right_user and right_language


def _merle_exercises(user):
    right_user = (
        user.invitation_code == "Merle"
        or user.invitation_code == "MerleITU"
        or user.invitation_code == "PTCT"
        or user.invitation_code == "zeeguu-preview"
        or user.id in [534, 2953, 4022, 4089, 4607]
    )
    return right_user

def _exercise_levels(user):
    right_user = (
        user.invitation_code == "exercise_levels"
        or user.is_member_of_cohort in [437, 514, 451, 519, 475, 506, 523]
        or user.id in [4192]
    )
    return right_user


def _no_audio_exercises(user):
    return user.is_member_of_cohort(447)


def _audio_exercises(user):
    return user.is_member_of_cohort(444)


def _extension_experiment_1(user):
    return (
        (user.is_member_of_cohort(437))
        or user.id in [3372, 3373, 2953, 3427, 2705]
        or user.id > 3555
    )
